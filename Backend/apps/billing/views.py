import logging

import stripe
from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.apikeys.constants import PLAN_LIMITS
from apps.apikeys.ratelimit import check_window
from apps.billing.constants import (
    ALREADY_PRO,
    BILLING_FAILED,
    BILLING_OFF,
    BILLING_TOO_MANY,
    DEMO_BILLING_LOCKED,
    NO_SUBSCRIPTION,
    PRO_PRICE_LABEL,
    SESSION_LIMIT,
    SYNC_EVENTS,
)
from apps.billing.models import BillingAccount
from apps.billing.services import (
    AlreadySubscribed,
    billing_enabled,
    create_checkout_url,
    create_portal_url,
    sync_customer,
)
from apps.users.constants import DEMO_EMAIL

logger = logging.getLogger(__name__)


def is_demo(user):
    return user.email.lower() == DEMO_EMAIL


def detail(message, code):
    return Response({"detail": message}, status=code)


class BillingAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        # Answer before touching the billing table, so a deploy without Stripe needs no migration.
        if not billing_enabled():
            return Response({"enabled": False})
        user = request.user
        account = BillingAccount.objects.filter(user=user).first()
        return Response(
            {
                "enabled": True,
                "test_mode": settings.STRIPE_SECRET_KEY.startswith("sk_test_"),
                "is_demo": is_demo(user),
                "plan": user.plan,
                "price": PRO_PRICE_LABEL,
                "limits": PLAN_LIMITS,
                "status": account.status if account else "",
                "current_period_end": account.current_period_end if account else None,
                "cancels_at": account.cancels_at if account else None,
                "can_manage": bool(account and account.stripe_subscription_id),
            }
        )


class BillingSessionAPIView(APIView):
    """Shared guards for the two endpoints that send the user off to Stripe."""

    permission_classes = (IsAuthenticated,)

    def create_url(self, user):
        raise NotImplementedError

    def post(self, request, *args, **kwargs):
        if not billing_enabled():
            return detail(BILLING_OFF, status.HTTP_503_SERVICE_UNAVAILABLE)
        if is_demo(request.user):
            return detail(DEMO_BILLING_LOCKED, status.HTTP_403_FORBIDDEN)
        limit, window = SESSION_LIMIT
        if not check_window(request.user.pk, "billing", limit, window).allowed:
            return detail(BILLING_TOO_MANY, status.HTTP_429_TOO_MANY_REQUESTS)
        try:
            return self.create_url(request.user)
        except stripe.StripeError:
            logger.exception("Stripe request failed")
            return detail(BILLING_FAILED, status.HTTP_502_BAD_GATEWAY)


class CheckoutAPIView(BillingSessionAPIView):
    def create_url(self, user):
        try:
            return Response({"url": create_checkout_url(user)})
        except AlreadySubscribed:
            return detail(ALREADY_PRO, status.HTTP_409_CONFLICT)


class PortalAPIView(BillingSessionAPIView):
    def create_url(self, user):
        account = BillingAccount.objects.filter(user=user).first()
        if account is None or not account.stripe_subscription_id:
            return detail(NO_SUBSCRIPTION, status.HTTP_409_CONFLICT)
        return Response({"url": create_portal_url(account)})


class StripeWebhookAPIView(APIView):
    """Stripe calls this directly, so the signature is the only proof of who sent it."""

    authentication_classes = ()
    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        if not billing_enabled():
            return detail(BILLING_OFF, status.HTTP_503_SERVICE_UNAVAILABLE)
        try:
            event = stripe.Webhook.construct_event(
                request.body,
                request.META.get("HTTP_STRIPE_SIGNATURE", ""),
                settings.STRIPE_WEBHOOK_SECRET,
            )
        except (ValueError, stripe.SignatureVerificationError):
            return detail("Invalid signature.", status.HTTP_400_BAD_REQUEST)

        if event["type"] in SYNC_EVENTS:
            customer_id = event["data"]["object"]["customer"]
            if customer_id:
                try:
                    sync_customer(customer_id)
                except stripe.StripeError:
                    # Any non-2xx makes Stripe send the event again later.
                    logger.exception("Stripe sync failed for event %s", event["id"])
                    return detail(BILLING_FAILED, status.HTTP_502_BAD_GATEWAY)
        return Response({"received": True})
