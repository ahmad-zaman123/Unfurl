from urllib.parse import urlencode

from django.conf import settings
from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.apikeys.authentication import ApiKeyAuthentication
from apps.apikeys.models import ApiKey, KeyUsageDay
from apps.apikeys.ratelimit import (
    apply_headers,
    check_api_key_limits,
    monthly_quota,
    monthly_usage,
)
from apps.cards.serializers import CardSpecSerializer
from apps.cards.services.cache import get_cached_png, record_hit, record_miss, store_png
from apps.cards.services.renderer import render_card
from apps.cards.services.signing import sign, verify

OG_PATH = "/api/v1/og"


def _public_base(request):
    configured = getattr(settings, "UNFURL_PUBLIC_BASE_URL", "")
    if configured:
        return configured.rstrip("/")
    return request.build_absolute_uri("/").rstrip("/")


class CardCreateAPIView(APIView):
    """Authenticated: validate a card spec and return a signed, public image URL."""

    authentication_classes = (ApiKeyAuthentication, JWTAuthentication)
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        # Rate limiting applies only to API-key traffic — the metered surface.
        # Dashboard (JWT) previews are the owner's own and stay unlimited.
        api_key = request.auth if isinstance(request.auth, ApiKey) else None
        result = check_api_key_limits(api_key) if api_key else None
        if result and not result.allowed:
            response = Response(
                {"detail": "Rate limit exceeded. Please retry later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
            return apply_headers(response, result)

        if api_key and monthly_usage(request.user) >= monthly_quota(request.user):
            return Response(
                {"detail": "Monthly quota exceeded for your plan."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        serializer = CardSpecSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        params = {
            key: str(value)
            for key, value in serializer.validated_data.items()
            if str(value) != ""
        }
        params["sig"] = sign({key: value for key, value in params.items()})
        url = _public_base(request) + OG_PATH + "?" + urlencode(params)

        if api_key:
            KeyUsageDay.record(api_key)

        response = Response({"url": url})
        if result:
            apply_headers(response, result)
        return response


class OGImageAPIView(APIView):
    """Public + cacheable: render a PNG from signed query parameters."""

    permission_classes = (AllowAny,)

    @extend_schema(
        parameters=[
            OpenApiParameter("template", str),
            OpenApiParameter("theme", str),
            OpenApiParameter("accent", str),
            OpenApiParameter("title", str),
            OpenApiParameter("subtitle", str),
            OpenApiParameter("eyebrow", str),
            OpenApiParameter("footer", str),
            OpenApiParameter("price", str),
            OpenApiParameter("date", str),
            OpenApiParameter("location", str),
            OpenApiParameter("sig", str),
        ],
        responses={(200, "image/png"): bytes},
    )
    def get(self, request, *args, **kwargs):
        provided = {key: value for key, value in request.query_params.items() if key != "sig"}
        signature = request.query_params.get("sig")
        if not verify(provided, signature):
            raise PermissionDenied("Invalid or missing signature.")

        # The signature is a deterministic hash of the params, so it doubles as
        # a perfect content-cache key: identical cards → one render, then hits.
        png = get_cached_png(signature)
        cache_state = "HIT"
        if png is None:
            serializer = CardSpecSerializer(data=provided)
            serializer.is_valid(raise_exception=True)
            png = render_card(**serializer.validated_data)
            store_png(signature, png)
            record_miss()
            cache_state = "MISS"
        else:
            record_hit()

        response = HttpResponse(png, content_type="image/png")
        response["Cache-Control"] = "public, max-age=86400"
        response["X-Cache"] = cache_state
        return response
