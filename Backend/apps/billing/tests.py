import json
import time
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import stripe
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.apikeys.ratelimit import monthly_quota
from apps.billing.constants import ALREADY_PRO, DEMO_BILLING_LOCKED, NO_SUBSCRIPTION, SESSION_LIMIT
from apps.billing.models import BillingAccount
from apps.users.choices import Plan
from apps.users.constants import DEMO_EMAIL
from apps.users.models import User

BILLING = "/api/billing/"
CHECKOUT = "/api/billing/checkout/"
PORTAL = "/api/billing/portal/"
WEBHOOK = "/api/billing/webhook/"
WEBHOOK_SECRET = "whsec_test"
PERIOD_END = 1893456000


def subscription(status="active", sub_id="sub_1", cancel_at=None, cancel_at_period_end=False):
    return {
        "id": sub_id,
        "object": "subscription",
        "status": status,
        "cancel_at": cancel_at,
        "cancel_at_period_end": cancel_at_period_end,
        "items": {"object": "list", "data": [{"object": "subscription_item", "current_period_end": PERIOD_END}]},
    }


class FakeStripe(stripe.HTTPClient):
    """Stands in for Stripe's servers, so these tests run the real SDK and its request format."""

    name = "fake"

    def __init__(self):
        super().__init__()
        self.subscriptions = []
        self.calls = []
        self.fail = False
        self.sessions = 0

    def request(self, method, url, headers, post_data=None, *, _usage=None):
        path = urlsplit(url).path
        params = parse_qs(post_data.decode() if isinstance(post_data, bytes) else post_data or "")
        self.calls.append((method, path, params, headers))
        if self.fail:
            return json.dumps({"error": {"message": "down", "type": "api_error"}}), 500, {}
        return json.dumps(self.respond(method, path, params)), 200, {}

    def respond(self, method, path, params):
        if path == "/v1/customers":
            return {"id": "cus_1", "object": "customer"}
        if path == "/v1/subscriptions":
            return {"object": "list", "data": self.subscriptions, "has_more": False, "url": path}
        if path == "/v1/billing_portal/sessions":
            return {"id": "bps_1", "object": "billing_portal.session", "url": "https://stripe.test/portal"}
        if path == "/v1/checkout/sessions":
            self.sessions += 1
            return {"id": f"cs_{self.sessions}", "object": "checkout.session", "url": "https://stripe.test/pay"}
        if path.endswith("/expire"):
            return {"id": path.split("/")[-2], "object": "checkout.session"}
        raise AssertionError(f"Unexpected Stripe call: {method} {path}")

    def paths(self):
        return [path for _, path, _, _ in self.calls]

    def close(self):
        pass


@override_settings(
    STRIPE_SECRET_KEY="sk_test_x",
    STRIPE_WEBHOOK_SECRET=WEBHOOK_SECRET,
    STRIPE_PRO_PRICE_ID="price_pro",
    APP_URL="https://app.example",
)
class BillingTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.stripe = FakeStripe()
        client = stripe.StripeClient("sk_test_x", http_client=self.stripe, max_network_retries=0)
        patcher = patch("apps.billing.services.get_client", return_value=client)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.user = User.objects.create_user(email="sara@example.com", password="first-password-1")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def account(self, **fields):
        return BillingAccount.objects.create(user=self.user, stripe_customer_id="cus_1", **fields)

    def post_event(self, event_type="customer.subscription.updated", customer="cus_1", secret=WEBHOOK_SECRET):
        payload = json.dumps(
            {"id": "evt_1", "object": "event", "type": event_type, "data": {"object": {"customer": customer}}}
        )
        timestamp = int(time.time())
        signature = stripe.WebhookSignature._compute_signature(f"{timestamp}.{payload}", secret)
        return APIClient().post(
            WEBHOOK,
            payload,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE=f"t={timestamp},v1={signature}",
        )


class CheckoutTests(BillingTestCase):
    def test_returns_a_subscription_checkout_for_the_pro_price(self):
        response = self.client.post(CHECKOUT)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["url"], "https://stripe.test/pay")
        _, _, params, _ = next(call for call in self.stripe.calls if call[1] == "/v1/checkout/sessions")
        self.assertEqual(params["mode"], ["subscription"])
        self.assertEqual(params["customer"], ["cus_1"])
        self.assertEqual(params["line_items[0][price]"], ["price_pro"])
        self.assertEqual(params["success_url"], ["https://app.example/?billing=success"])

    def test_starting_checkout_does_not_upgrade_the_user(self):
        self.client.post(CHECKOUT)
        self.user.refresh_from_db()
        self.assertEqual(self.user.plan, Plan.FREE)

    def test_reuses_the_stripe_customer(self):
        self.client.post(CHECKOUT)
        self.client.post(CHECKOUT)
        self.assertEqual(self.stripe.paths().count("/v1/customers"), 1)
        self.assertEqual(BillingAccount.objects.count(), 1)

    def test_customer_creation_is_idempotent_per_user(self):
        self.client.post(CHECKOUT)
        _, _, _, headers = next(call for call in self.stripe.calls if call[1] == "/v1/customers")
        self.assertEqual(headers["Idempotency-Key"], f"unfurl-customer-{self.user.pk}")

    def test_a_new_checkout_closes_the_previous_one(self):
        self.client.post(CHECKOUT)
        self.client.post(CHECKOUT)
        self.assertIn("/v1/checkout/sessions/cs_1/expire", self.stripe.paths())

    def test_refuses_a_second_subscription_even_before_the_webhook_arrives(self):
        self.account()
        self.stripe.subscriptions = [subscription()]
        response = self.client.post(CHECKOUT)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["detail"], ALREADY_PRO)
        self.assertNotIn("/v1/checkout/sessions", self.stripe.paths())
        self.user.refresh_from_db()
        self.assertEqual(self.user.plan, Plan.PRO)

    def test_demo_account_cannot_check_out(self):
        self.user.email = DEMO_EMAIL
        self.user.save()
        response = self.client.post(CHECKOUT)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["detail"], DEMO_BILLING_LOCKED)
        self.assertEqual(self.stripe.calls, [])

    def test_stripe_outage_returns_502_without_leaking_details(self):
        self.stripe.fail = True
        response = self.client.post(CHECKOUT)
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("down", response.data["detail"])

    def test_requires_sign_in(self):
        self.assertEqual(APIClient().post(CHECKOUT).status_code, 401)

    def test_rate_limited(self):
        limit, _ = SESSION_LIMIT
        for _ in range(limit):
            self.client.post(CHECKOUT)
        self.assertEqual(self.client.post(CHECKOUT).status_code, 429)

    @override_settings(STRIPE_SECRET_KEY="")
    def test_off_without_stripe_settings(self):
        self.assertEqual(self.client.post(CHECKOUT).status_code, 503)
        self.assertEqual(self.client.post(PORTAL).status_code, 503)
        self.assertEqual(self.client.get(BILLING).data, {"enabled": False})


class PortalTests(BillingTestCase):
    def test_returns_portal_url_back_to_the_app(self):
        self.account(stripe_subscription_id="sub_1", status="active")
        response = self.client.post(PORTAL)
        self.assertEqual(response.data["url"], "https://stripe.test/portal")
        _, _, params, _ = self.stripe.calls[-1]
        self.assertEqual(params["customer"], ["cus_1"])
        self.assertEqual(params["return_url"], ["https://app.example/"])

    def test_refused_without_a_subscription(self):
        response = self.client.post(PORTAL)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["detail"], NO_SUBSCRIPTION)
        self.account()
        self.assertEqual(self.client.post(PORTAL).status_code, 409)
        self.assertEqual(self.stripe.calls, [])


class WebhookTests(BillingTestCase):
    def plan(self):
        self.user.refresh_from_db()
        return self.user.plan

    def test_rejects_a_bad_signature(self):
        self.account()
        self.stripe.subscriptions = [subscription()]
        response = self.post_event(secret="whsec_wrong")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.plan(), Plan.FREE)
        self.assertEqual(self.stripe.calls, [])

    def test_rejects_a_missing_signature(self):
        response = APIClient().post(WEBHOOK, "{}", content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_rejects_an_old_replayed_signature(self):
        payload = "{}"
        timestamp = int(time.time()) - 3600
        signature = stripe.WebhookSignature._compute_signature(f"{timestamp}.{payload}", WEBHOOK_SECRET)
        response = APIClient().post(
            WEBHOOK, payload, content_type="application/json", HTTP_STRIPE_SIGNATURE=f"t={timestamp},v1={signature}"
        )
        self.assertEqual(response.status_code, 400)

    def test_paid_checkout_upgrades_and_raises_the_quota(self):
        self.account()
        self.stripe.subscriptions = [subscription()]
        self.assertEqual(self.post_event("checkout.session.completed").status_code, 200)
        self.assertEqual(self.plan(), Plan.PRO)
        self.assertEqual(monthly_quota(self.user), 2000000)
        account = BillingAccount.objects.get(user=self.user)
        self.assertEqual(account.stripe_subscription_id, "sub_1")
        self.assertEqual(int(account.current_period_end.timestamp()), PERIOD_END)

    def test_canceled_subscription_downgrades(self):
        self.account()
        self.stripe.subscriptions = [subscription()]
        self.post_event()
        self.stripe.subscriptions = [subscription("canceled")]
        self.post_event("customer.subscription.deleted")
        self.assertEqual(self.plan(), Plan.FREE)
        self.assertEqual(monthly_quota(self.user), 50000)

    def test_failed_renewal_keeps_pro_while_stripe_retries(self):
        self.account()
        self.stripe.subscriptions = [subscription("past_due")]
        self.post_event()
        self.assertEqual(self.plan(), Plan.PRO)
        self.stripe.subscriptions = [subscription("unpaid")]
        self.post_event()
        self.assertEqual(self.plan(), Plan.FREE)

    def test_unfinished_first_payment_does_not_upgrade(self):
        self.account()
        self.stripe.subscriptions = [subscription("incomplete")]
        self.post_event()
        self.assertEqual(self.plan(), Plan.FREE)

    def test_a_late_event_cannot_undo_a_newer_state(self):
        # An "updated" event from while it was active arrives after the cancellation.
        self.account()
        self.stripe.subscriptions = [subscription("canceled")]
        self.post_event("customer.subscription.updated")
        self.assertEqual(self.plan(), Plan.FREE)

    def test_duplicate_events_are_harmless(self):
        self.account()
        self.stripe.subscriptions = [subscription()]
        self.post_event()
        self.post_event()
        self.assertEqual(self.plan(), Plan.PRO)
        self.assertEqual(BillingAccount.objects.count(), 1)

    def test_a_canceled_subscription_does_not_hide_a_live_one(self):
        self.account()
        self.stripe.subscriptions = [subscription("canceled", "sub_new"), subscription("active", "sub_old")]
        self.post_event()
        self.assertEqual(self.plan(), Plan.PRO)
        self.assertEqual(BillingAccount.objects.get(user=self.user).stripe_subscription_id, "sub_old")

    def test_scheduled_cancellation_stays_pro_and_records_the_date(self):
        self.account()
        self.stripe.subscriptions = [subscription(cancel_at_period_end=True)]
        self.post_event()
        self.assertEqual(self.plan(), Plan.PRO)
        account = BillingAccount.objects.get(user=self.user)
        self.assertEqual(int(account.cancels_at.timestamp()), PERIOD_END)

        self.stripe.subscriptions = [subscription(cancel_at=PERIOD_END + 60)]
        self.post_event()
        account.refresh_from_db()
        self.assertEqual(int(account.cancels_at.timestamp()), PERIOD_END + 60)

    def test_ignores_customers_that_are_not_ours(self):
        self.assertEqual(self.post_event(customer="cus_other").status_code, 200)
        self.assertEqual(self.stripe.calls, [])

    def test_ignores_other_event_types(self):
        self.account()
        self.stripe.subscriptions = [subscription()]
        self.assertEqual(self.post_event("invoice.created").status_code, 200)
        self.assertEqual(self.stripe.calls, [])

    def test_stripe_outage_asks_for_a_retry(self):
        self.account()
        self.stripe.fail = True
        self.assertEqual(self.post_event().status_code, 502)
        self.assertEqual(self.plan(), Plan.FREE)


class BillingStatusTests(BillingTestCase):
    def test_free_user(self):
        data = self.client.get(BILLING).data
        self.assertEqual(data["plan"], Plan.FREE)
        self.assertTrue(data["enabled"])
        self.assertTrue(data["test_mode"])
        self.assertFalse(data["can_manage"])
        self.assertEqual(data["limits"]["pro"]["per_month"], 2000000)

    def test_subscribed_user(self):
        self.account()
        self.stripe.subscriptions = [subscription()]
        self.post_event()
        self.user.refresh_from_db()
        data = self.client.get(BILLING).data
        self.assertEqual(data["plan"], Plan.PRO)
        self.assertEqual(data["status"], "active")
        self.assertTrue(data["can_manage"])
        self.assertIsNotNone(data["current_period_end"])

    def test_never_exposes_stripe_ids(self):
        self.account(stripe_subscription_id="sub_1", checkout_session_id="cs_1")
        self.assertNotIn("_1", json.dumps(self.client.get(BILLING).data, default=str))

    def test_requires_sign_in(self):
        self.assertEqual(APIClient().get(BILLING).status_code, 401)
