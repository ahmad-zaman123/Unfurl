from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.apikeys.models import ApiKey, KeyUsageDay
from apps.apikeys.ratelimit import monthly_quota, monthly_usage
from apps.apikeys.serializers import ApiKeyCreateSerializer, ApiKeySerializer
from apps.cards.services.cache import cache_stats

USAGE_WINDOW_DAYS = 14


class ApiKeyListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = (IsAuthenticated,)

    def get_queryset(self, *args, **kwargs):
        return self.request.user.api_keys.all()

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ApiKeyCreateSerializer
        return ApiKeySerializer

    def create(self, request, *args, **kwargs):
        serializer = ApiKeyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance, raw_key = ApiKey.generate(
            owner=request.user,
            name=serializer.validated_data["name"],
        )
        # The raw key is returned exactly once, at creation time.
        data = ApiKeySerializer(instance).data
        data["key"] = raw_key
        return Response(data, status=status.HTTP_201_CREATED)


class ApiKeyRevokeAPIView(generics.DestroyAPIView):
    permission_classes = (IsAuthenticated,)

    def get_queryset(self, *args, **kwargs):
        return self.request.user.api_keys.all()

    def perform_destroy(self, instance):
        # Soft-revoke so the key can never be re-used but the record survives.
        if instance.revoked_at is None:
            instance.revoked_at = timezone.now()
            instance.save(update_fields=("revoked_at", "modified"))


class UsageAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        user = request.user
        today = timezone.now().date()
        start = today - timedelta(days=USAGE_WINDOW_DAYS - 1)
        usage = KeyUsageDay.objects.filter(owner=user)

        # Daily totals across all the user's keys, gap-filled to a full window.
        per_day = {
            row["date"]: row["total"]
            for row in usage.filter(date__gte=start).values("date").annotate(total=Sum("count"))
        }
        series = [
            {"date": (start + timedelta(days=offset)).isoformat(),
             "count": per_day.get(start + timedelta(days=offset), 0)}
            for offset in range(USAGE_WINDOW_DAYS)
        ]

        per_key = [
            {"name": row["api_key__name"], "prefix": row["api_key__prefix"], "count": row["total"]}
            for row in usage.values("api_key__name", "api_key__prefix")
            .annotate(total=Sum("count"))
            .order_by("-total")
        ]

        total_calls = usage.aggregate(total=Sum("count"))["total"] or 0
        calls_today = per_day.get(today, 0)
        active_keys = user.api_keys.filter(revoked_at__isnull=True).count()

        return Response(
            {
                "summary": {
                    "total_calls": total_calls,
                    "calls_today": calls_today,
                    "active_keys": active_keys,
                    "plan": user.plan,
                    "month_used": monthly_usage(user),
                    "month_quota": monthly_quota(user),
                    "cache": cache_stats(),
                },
                "series": series,
                "per_key": per_key,
            }
        )
