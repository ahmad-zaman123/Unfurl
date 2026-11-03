from datetime import datetime, timezone

import stripe
from django.conf import settings
from django.db import transaction

from apps.billing.constants import PRO_STATUSES
from apps.billing.models import BillingAccount
from apps.users.choices import Plan

REQUEST_TIMEOUT_SECONDS = 10


class AlreadySubscribed(Exception):
    pass


def billing_enabled():
    return bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_WEBHOOK_SECRET and settings.STRIPE_PRO_PRICE_ID)


def get_client():
    return stripe.StripeClient(
        settings.STRIPE_SECRET_KEY,
        http_client=stripe.RequestsClient(timeout=REQUEST_TIMEOUT_SECONDS),
    )


def _as_datetime(timestamp):
    return datetime.fromtimestamp(timestamp, tz=timezone.utc) if timestamp else None


def sync_customer(customer_id):
    """Copy a customer's current subscription from Stripe onto our records.

    The row stays locked while Stripe answers, so two webhooks at once can't write older
    data over newer. Returns None for a customer that isn't ours.
    """
    with transaction.atomic():
        account = BillingAccount.objects.select_for_update().filter(stripe_customer_id=customer_id).first()
        if account is None:
            return None

        subscriptions = get_client().v1.subscriptions.list({"customer": customer_id, "status": "all"}).data
        # Stripe lists newest first. Prefer one that's still live over a newer canceled one.
        current = next(
            (sub for sub in subscriptions if sub["status"] in PRO_STATUSES),
            subscriptions[0] if subscriptions else None,
        )

        is_pro = False
        if current is None:
            account.stripe_subscription_id = ""
            account.status = ""
            account.current_period_end = None
            account.cancels_at = None
        else:
            is_pro = current["status"] in PRO_STATUSES
            period_end = _as_datetime(current["items"]["data"][0]["current_period_end"])
            account.stripe_subscription_id = current["id"]
            account.status = current["status"]
            account.current_period_end = period_end
            # The portal can schedule a cancellation either way, depending on its settings.
            account.cancels_at = _as_datetime(current["cancel_at"]) or (
                period_end if current["cancel_at_period_end"] else None
            )
        account.save()

        user = account.user
        plan = Plan.PRO if is_pro else Plan.FREE
        if user.plan != plan:
            user.plan = plan
            user.save(update_fields=("plan", "modified"))
        return account


def _get_or_create_account(user):
    account = BillingAccount.objects.filter(user=user).first()
    if account:
        return account
    # The idempotency key means two requests at once still get a single Stripe customer.
    customer = get_client().v1.customers.create(
        {"email": user.email, "metadata": {"user_id": str(user.pk)}},
        {"idempotency_key": f"unfurl-customer-{user.pk}"},
    )
    account, _ = BillingAccount.objects.get_or_create(user=user, defaults={"stripe_customer_id": customer["id"]})
    return account


def _expire_open_session(account):
    """Close the last checkout, so paying in two tabs can't start two subscriptions."""
    if not account.checkout_session_id:
        return
    try:
        get_client().v1.checkout.sessions.expire(account.checkout_session_id)
    except stripe.InvalidRequestError:
        pass  # Already finished or expired.


def create_checkout_url(user):
    account = _get_or_create_account(user)
    # A webhook may still be on its way, so ask Stripe before taking another payment.
    account = sync_customer(account.stripe_customer_id)
    if account.status in PRO_STATUSES:
        raise AlreadySubscribed
    _expire_open_session(account)
    session = get_client().v1.checkout.sessions.create(
        {
            "mode": "subscription",
            "customer": account.stripe_customer_id,
            "client_reference_id": str(user.pk),
            "line_items": [{"price": settings.STRIPE_PRO_PRICE_ID, "quantity": 1}],
            "success_url": f"{settings.APP_URL}/?billing=success",
            "cancel_url": f"{settings.APP_URL}/?billing=cancelled",
        }
    )
    account.checkout_session_id = session["id"]
    account.save(update_fields=("checkout_session_id", "modified"))
    return session["url"]


def create_portal_url(account):
    session = get_client().v1.billing_portal.sessions.create(
        {"customer": account.stripe_customer_id, "return_url": f"{settings.APP_URL}/"}
    )
    return session["url"]
