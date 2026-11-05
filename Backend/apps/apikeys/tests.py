from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.apikeys.constants import KEY_DISPLAY_LEN, PLAN_LIMITS
from apps.apikeys.models import ApiKey, KeyUsageDay, hash_key
from apps.apikeys.ratelimit import check_window, monthly_usage, plan_limits
from apps.users.models import User

KEYS = "/api/keys/"
USAGE = "/api/usage/"
CARDS = "/api/v1/cards"
SPEC = {"title": "Hello"}


def jwt(user):
    return {"HTTP_AUTHORIZATION": f"Bearer {RefreshToken.for_user(user).access_token}"}


def bearer(raw_key):
    return {"HTTP_AUTHORIZATION": f"Bearer {raw_key}"}


class KeyTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(email="sara@example.com", password="first-password-1")
        self.other = User.objects.create_user(email="omar@example.com", password="first-password-1")


class ApiKeyTests(KeyTestCase):
    def test_new_key_is_shown_once_and_stored_hashed(self):
        response = self.client.post(KEYS, {"name": "Production"}, format="json", **jwt(self.user))
        self.assertEqual(response.status_code, 201)
        raw = response.json()["key"]
        self.assertTrue(raw.startswith("sk_live_"))
        key = ApiKey.objects.get(owner=self.user)
        self.assertEqual(key.hashed_key, hash_key(raw))
        self.assertEqual(key.prefix, raw[:KEY_DISPLAY_LEN])
        self.assertNotIn(raw, [key.hashed_key, key.prefix, key.name])

        listed = self.client.get(KEYS, **jwt(self.user)).json()
        self.assertEqual(len(listed), 1)
        self.assertNotIn("key", listed[0])
        self.assertNotIn("hashed_key", listed[0])

    def test_each_key_is_different(self):
        _, first = ApiKey.generate(owner=self.user, name="a")
        _, second = ApiKey.generate(owner=self.user, name="b")
        self.assertNotEqual(first, second)

    def test_a_name_is_required(self):
        response = self.client.post(KEYS, {}, format="json", **jwt(self.user))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ApiKey.objects.exists())

    def test_people_only_see_and_revoke_their_own_keys(self):
        theirs, _ = ApiKey.generate(owner=self.other, name="Theirs")
        ApiKey.generate(owner=self.user, name="Mine")
        names = [k["name"] for k in self.client.get(KEYS, **jwt(self.user)).json()]
        self.assertEqual(names, ["Mine"])
        response = self.client.delete(f"{KEYS}{theirs.id}/", **jwt(self.user))
        self.assertEqual(response.status_code, 404)
        theirs.refresh_from_db()
        self.assertIsNone(theirs.revoked_at)

    def test_revoking_keeps_the_record_and_stops_the_key(self):
        key, raw = ApiKey.generate(owner=self.user, name="Production")
        self.assertEqual(self.client.post(CARDS, SPEC, format="json", **bearer(raw)).status_code, 200)

        self.assertEqual(self.client.delete(f"{KEYS}{key.id}/", **jwt(self.user)).status_code, 204)
        key.refresh_from_db()
        revoked_at = key.revoked_at
        self.assertIsNotNone(revoked_at)

        # Revoking again is harmless and keeps the first time.
        self.assertEqual(self.client.delete(f"{KEYS}{key.id}/", **jwt(self.user)).status_code, 204)
        key.refresh_from_db()
        self.assertEqual(key.revoked_at, revoked_at)

        response = self.client.post(CARDS, SPEC, format="json", **bearer(raw))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "This API key has been revoked.")
        self.assertFalse(self.client.get(KEYS, **jwt(self.user)).json()[0]["is_active"])

    def test_unknown_key_is_refused(self):
        response = self.client.post(CARDS, SPEC, format="json", **bearer("sk_live_not-a-real-key"))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Invalid API key.")
        self.assertEqual(response["WWW-Authenticate"], "Bearer")

    def test_using_a_key_records_when(self):
        key, raw = ApiKey.generate(owner=self.user, name="Production")
        self.client.post(CARDS, SPEC, format="json", **bearer(raw))
        key.refresh_from_db()
        self.assertIsNotNone(key.last_used_at)

    def test_an_api_key_cannot_manage_keys(self):
        key, raw = ApiKey.generate(owner=self.user, name="Production")
        self.assertEqual(self.client.get(KEYS, **bearer(raw)).status_code, 401)
        self.assertEqual(self.client.post(KEYS, {"name": "x"}, format="json", **bearer(raw)).status_code, 401)
        self.assertEqual(self.client.delete(f"{KEYS}{key.id}/", **bearer(raw)).status_code, 401)
        self.assertEqual(self.client.get(USAGE, **bearer(raw)).status_code, 401)
        self.assertEqual(ApiKey.objects.count(), 1)

    def test_signed_out_requests_are_refused(self):
        self.assertEqual(self.client.get(KEYS).status_code, 401)
        self.assertEqual(self.client.post(CARDS, SPEC, format="json").status_code, 401)


class UsageTests(KeyTestCase):
    def test_usage_is_counted_per_key_per_day(self):
        key, _ = ApiKey.generate(owner=self.user, name="Production")
        for _ in range(3):
            KeyUsageDay.record(key)
        row = KeyUsageDay.objects.get(api_key=key)
        self.assertEqual((row.date, row.count, row.owner_id), (timezone.now().date(), 3, self.user.id))

    def test_usage_page_fills_gaps_and_totals_by_key(self):
        production, _ = ApiKey.generate(owner=self.user, name="Production")
        staging, _ = ApiKey.generate(owner=self.user, name="Staging")
        theirs, _ = ApiKey.generate(owner=self.other, name="Theirs")
        today = timezone.now().date()
        KeyUsageDay.objects.create(api_key=production, owner=self.user, date=today, count=5)
        KeyUsageDay.objects.create(api_key=production, owner=self.user, date=today - timedelta(days=3), count=7)
        KeyUsageDay.objects.create(api_key=staging, owner=self.user, date=today, count=2)
        KeyUsageDay.objects.create(api_key=theirs, owner=self.other, date=today, count=99)
        staging.revoked_at = timezone.now()
        staging.save()

        data = self.client.get(USAGE, **jwt(self.user)).json()
        series = data["series"]
        self.assertEqual(len(series), 14)
        self.assertEqual(series[-1], {"date": today.isoformat(), "count": 7})
        self.assertEqual(series[-4]["count"], 7)
        self.assertEqual(sum(day["count"] for day in series), 14)
        self.assertEqual([(k["name"], k["count"]) for k in data["per_key"]], [("Production", 12), ("Staging", 2)])
        summary = data["summary"]
        self.assertEqual(summary["total_calls"], 14)
        self.assertEqual(summary["calls_today"], 7)
        self.assertEqual(summary["active_keys"], 1)
        self.assertEqual(summary["plan"], "free")
        self.assertEqual(summary["month_quota"], PLAN_LIMITS["free"]["per_month"])

    def test_monthly_usage_ignores_last_month(self):
        key, _ = ApiKey.generate(owner=self.user, name="Production")
        first_of_month = timezone.now().date().replace(day=1)
        KeyUsageDay.objects.create(api_key=key, owner=self.user, date=first_of_month, count=4)
        KeyUsageDay.objects.create(api_key=key, owner=self.user, date=first_of_month - timedelta(days=1), count=50)
        self.assertEqual(monthly_usage(self.user), 4)


class RateLimitTests(KeyTestCase):
    def setUp(self):
        super().setUp()
        self.key, self.raw = ApiKey.generate(owner=self.user, name="Production")

    def card(self, **headers):
        return self.client.post(CARDS, SPEC, format="json", **(headers or bearer(self.raw)))

    def test_window_counts_and_resets(self):
        with patch("apps.apikeys.ratelimit.time.time", return_value=1_000_020):
            results = [check_window("k", "test", 2, 60) for _ in range(3)]
        self.assertEqual([r.allowed for r in results], [True, True, False])
        self.assertEqual([r.remaining for r in results], [1, 0, 0])
        self.assertEqual(results[2].reset, 1_000_020 - 1_000_020 % 60 + 60)
        self.assertEqual(results[2].retry_after, results[2].reset - 1_000_020)
        with patch("apps.apikeys.ratelimit.time.time", return_value=1_000_020 + 60):
            self.assertTrue(check_window("k", "test", 2, 60).allowed)

    def test_windows_are_separate_per_key_and_scope(self):
        self.assertTrue(check_window("a", "test", 1, 60).allowed)
        self.assertTrue(check_window("b", "test", 1, 60).allowed)
        self.assertTrue(check_window("a", "other", 1, 60).allowed)
        self.assertFalse(check_window("a", "test", 1, 60).allowed)

    def test_responses_carry_rate_limit_headers(self):
        response = self.card()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-RateLimit-Limit"], "60")
        self.assertEqual(response["X-RateLimit-Remaining"], "59")
        self.assertIn("X-RateLimit-Reset", response)
        self.assertNotIn("Retry-After", response)

    def test_per_minute_limit_blocks_and_does_not_count(self):
        with patch.dict(PLAN_LIMITS["free"], {"per_minute": 2}):
            self.assertEqual(self.card().status_code, 200)
            self.assertEqual(self.card().status_code, 200)
            blocked = self.card()
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(blocked.json()["detail"], "Rate limit exceeded. Please retry later.")
        self.assertEqual(blocked["X-RateLimit-Remaining"], "0")
        self.assertGreaterEqual(int(blocked["Retry-After"]), 1)
        self.assertEqual(KeyUsageDay.objects.get(api_key=self.key).count, 2)

    def test_per_day_limit_blocks(self):
        with patch.dict(PLAN_LIMITS["free"], {"per_day": 1}):
            self.assertEqual(self.card().status_code, 200)
            self.assertEqual(self.card().status_code, 429)

    def test_limits_are_per_key(self):
        _, second = ApiKey.generate(owner=self.user, name="Staging")
        with patch.dict(PLAN_LIMITS["free"], {"per_minute": 1}):
            self.assertEqual(self.card().status_code, 200)
            self.assertEqual(self.card().status_code, 429)
            self.assertEqual(self.card(**bearer(second)).status_code, 200)

    def test_monthly_quota_is_shared_across_keys(self):
        KeyUsageDay.objects.create(
            api_key=self.key, owner=self.user, date=timezone.now().date(), count=PLAN_LIMITS["free"]["per_month"]
        )
        _, second = ApiKey.generate(owner=self.user, name="Staging")
        response = self.card(**bearer(second))
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["detail"], "Monthly quota exceeded for your plan.")

    def test_pro_plan_gets_higher_limits(self):
        self.user.plan = "pro"
        self.user.save()
        self.assertEqual(self.card()["X-RateLimit-Limit"], str(PLAN_LIMITS["pro"]["per_minute"]))
        self.assertEqual(plan_limits("unknown"), PLAN_LIMITS["free"])

    def test_dashboard_previews_are_not_limited_or_counted(self):
        with patch.dict(PLAN_LIMITS["free"], {"per_minute": 1}):
            for _ in range(3):
                response = self.card(**jwt(self.user))
                self.assertEqual(response.status_code, 200)
                self.assertNotIn("X-RateLimit-Limit", response)
        self.assertFalse(KeyUsageDay.objects.exists())

    def test_bad_requests_are_not_counted(self):
        response = self.client.post(CARDS, {"accent": "red"}, format="json", **bearer(self.raw))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(KeyUsageDay.objects.exists())
