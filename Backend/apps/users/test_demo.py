from datetime import timedelta
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.apikeys.models import ApiKey, KeyUsageDay
from apps.users.constants import DEMO_EMAIL, DEMO_FULL, DEMO_LIMITS, DEMO_PASSWORD_LOCKED, DEMO_TOO_MANY
from apps.users.demo import DEMO_DOMAIN, DEMO_LIFETIME, PURGE_BATCH, USAGE, is_demo_email
from apps.users.models import User
from apps.users.serializers import UserSerializer

DEMO = "/api/auth/demo/"


class DemoTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def start(self, ip="203.0.113.5"):
        return self.client.post(DEMO, REMOTE_ADDR=ip)

    def auth(self, access):
        return {"HTTP_AUTHORIZATION": f"Bearer {access}"}

    def test_me_says_whether_the_account_is_a_demo(self):
        me = self.client.get("/api/auth/me/", **self.auth(self.start().json()["access"])).json()
        self.assertIs(me["is_demo"], True)
        self.assertIs(UserSerializer(User(email="sara@example.com")).data["is_demo"], False)

    def demo_user(self, response):
        email = self.client.get("/api/auth/me/", **self.auth(response.json()["access"])).json()["email"]
        return User.objects.get(email=email)

    def test_demo_signs_in_a_new_user_with_keys_and_usage(self):
        response = self.start()
        self.assertEqual(response.status_code, 201)
        user = self.demo_user(response)
        self.assertTrue(user.email.endswith("@" + DEMO_DOMAIN))
        self.assertFalse(user.has_usable_password())
        self.assertEqual(sorted(ApiKey.objects.filter(owner=user).values_list("name", flat=True)), ["Production", "Staging"])
        days = KeyUsageDay.objects.filter(owner=user)
        self.assertEqual(days.count(), len(USAGE))
        self.assertEqual(sum(d.count for d in days), sum(USAGE))
        self.assertEqual(max(d.date for d in days), timezone.now().date())

    def test_each_visitor_sees_only_their_own_keys(self):
        first = self.start().json()["access"]
        second = self.start().json()["access"]
        mine = self.client.get("/api/keys/", **self.auth(first)).json()
        theirs = self.client.get("/api/keys/", **self.auth(second)).json()
        ids = lambda keys: {k["id"] for k in keys}  # noqa: E731
        self.assertEqual(len(ids(mine)), 2)
        self.assertFalse(ids(mine) & ids(theirs))

    def test_demo_is_limited_per_address(self):
        for _ in range(DEMO_LIMITS["demo_ip"][0]):
            self.assertEqual(self.start().status_code, 201)
        blocked = self.start()
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(blocked.json()["detail"], DEMO_TOO_MANY)
        self.assertEqual(self.start(ip="198.51.100.7").status_code, 201)

    def test_demo_has_a_daily_total(self):
        with mock.patch.dict(DEMO_LIMITS, {"demo_all": (2, 86400)}):
            self.assertEqual(self.start(ip="198.51.100.1").status_code, 201)
            self.assertEqual(self.start(ip="198.51.100.2").status_code, 201)
            blocked = self.start(ip="198.51.100.3")
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(blocked.json()["detail"], DEMO_FULL)

    def test_old_demos_are_removed_when_a_new_one_starts(self):
        old = self.demo_user(self.start())
        User.objects.filter(id=old.id).update(created=timezone.now() - DEMO_LIFETIME - timedelta(minutes=1))
        real = User.objects.create_user(email="real@example.com", password="real-password-1")
        self.start()
        self.assertFalse(User.objects.filter(id=old.id).exists())
        self.assertFalse(ApiKey.objects.filter(owner_id=old.id).exists())
        self.assertTrue(User.objects.filter(id=real.id).exists())

    def test_cleanup_is_done_in_batches(self):
        for i in range(PURGE_BATCH + 3):
            User.objects.create(email=f"demo-old{i}@{DEMO_DOMAIN}")
        User.objects.filter(email__endswith="@" + DEMO_DOMAIN).update(
            created=timezone.now() - DEMO_LIFETIME - timedelta(minutes=1)
        )
        self.start()
        self.assertEqual(User.objects.filter(email__endswith="@" + DEMO_DOMAIN).count(), 4)

    def test_demo_cannot_set_a_password(self):
        access = self.start().json()["access"]
        response = self.client.post(
            "/api/auth/password/", {"new_password": "a-new-password-1"}, format="json", **self.auth(access)
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], [DEMO_PASSWORD_LOCKED])

    @override_settings(EMAIL_HOST="smtp.example")
    def test_demo_gets_no_reset_email(self):
        email = self.demo_user(self.start()).email
        self.client.post("/api/auth/password/forgot/", {"email": email}, format="json")
        self.assertEqual(len(mail.outbox), 0)

    def test_demo_emails_are_recognised(self):
        self.assertTrue(is_demo_email(DEMO_EMAIL))
        self.assertTrue(is_demo_email(f"DEMO-abc@{DEMO_DOMAIN.upper()}"))
        self.assertFalse(is_demo_email("someone@example.com"))
        self.assertFalse(is_demo_email(f"someone@not{DEMO_DOMAIN}"))
