from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient

from apps.users.constants import DEMO_EMAIL, DEMO_PASSWORD_LOCKED, RESET_INVALID, RESET_LIMITS, RESET_SENT
from apps.users.models import User

FORGOT = "/api/auth/password/forgot/"
RESET = "/api/auth/password/reset/"
PASSWORD = "first-password-1"
NEW_PASSWORD = "second-password-2"


@override_settings(EMAIL_HOST="smtp.example", APP_URL="https://app.example")
class PasswordResetTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(email="sara@example.com", password=PASSWORD)

    def forgot(self, email="sara@example.com"):
        return self.client.post(FORGOT, {"email": email}, format="json")

    def link_parts(self):
        url = mail.outbox[-1].alternatives[0][0].split('href="')[1].split('"')[0].replace("&amp;", "&")
        query = url.split("?")[1]
        return dict(part.split("=") for part in query.split("&"))

    def reset(self, parts, password=NEW_PASSWORD):
        return self.client.post(RESET, {**parts, "new_password": password}, format="json")

    def sign_in(self, password=PASSWORD):
        return self.client.post("/api/auth/token/", {"email": "sara@example.com", "password": password}, format="json")

    def me(self, access):
        return self.client.get("/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {access}")

    def test_reply_is_the_same_for_known_and_unknown_emails(self):
        known, unknown = self.forgot(), self.forgot("nobody@example.com")
        self.assertEqual((known.status_code, unknown.status_code), (200, 200))
        self.assertEqual(known.json(), {"detail": RESET_SENT})
        self.assertEqual(known.json(), unknown.json())
        self.assertEqual([m.to for m in mail.outbox], [["sara@example.com"]])

    def test_email_has_plain_and_styled_parts_pointing_at_the_frontend(self):
        self.forgot("SARA@example.com")
        message = mail.outbox[0]
        self.assertIn("https://app.example/reset-password?uid=", message.body)
        html = message.alternatives[0][0]
        self.assertIn('href="https://app.example/reset-password?uid=', html)
        self.assertIn("sara@example.com", html)

    def test_link_ignores_a_forged_host_header(self):
        self.client.post(FORGOT, {"email": "sara@example.com"}, format="json", HTTP_HOST="evil.example")
        self.assertNotIn("evil.example", mail.outbox[0].body)

    def test_reset_changes_the_password_and_works_once(self):
        self.forgot()
        parts = self.link_parts()
        self.assertEqual(self.reset(parts).status_code, 200)
        self.assertEqual(self.sign_in().status_code, 401)
        self.assertEqual(self.sign_in(NEW_PASSWORD).status_code, 200)
        reused = self.reset(parts, "third-password-3")
        self.assertEqual(reused.status_code, 400)
        self.assertEqual(reused.json()["detail"], [RESET_INVALID])

    def test_reset_ends_existing_sessions(self):
        tokens = self.sign_in().json()
        self.assertEqual(self.me(tokens["access"]).status_code, 200)
        self.forgot()
        self.reset(self.link_parts())
        self.assertEqual(self.me(tokens["access"]).status_code, 401)
        refreshed = self.client.post("/api/auth/token/refresh/", {"refresh": tokens["refresh"]}, format="json")
        if refreshed.status_code == 200:
            self.assertEqual(self.me(refreshed.json()["access"]).status_code, 401)

    def test_expired_link_is_refused(self):
        self.forgot()
        with override_settings(PASSWORD_RESET_TIMEOUT=-1):
            self.assertEqual(self.reset(self.link_parts()).status_code, 400)
        self.assertEqual(self.sign_in().status_code, 200)

    def test_bad_links_are_refused(self):
        self.forgot()
        good = self.link_parts()
        for parts in (
            {"uid": good["uid"], "token": "wrong"},
            {"uid": "bm90LWEtdXVpZA", "token": good["token"]},
            {"uid": "!!!", "token": good["token"]},
        ):
            response = self.reset(parts)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json()["detail"], [RESET_INVALID])

    def test_weak_password_is_refused_and_the_link_still_works(self):
        self.forgot()
        parts = self.link_parts()
        weak = self.reset(parts, "password")
        self.assertEqual(weak.status_code, 400)
        self.assertIn("new_password", weak.json())
        self.assertEqual(self.reset(parts).status_code, 200)

    def test_demo_and_disabled_accounts_get_no_email(self):
        demo = User.objects.create_user(email=DEMO_EMAIL, password="demo1234")
        User.objects.create_user(email="off@example.com", password=PASSWORD, is_active=False)
        self.assertEqual(self.forgot(DEMO_EMAIL).json(), {"detail": RESET_SENT})
        self.assertEqual(self.forgot("off@example.com").json(), {"detail": RESET_SENT})
        self.assertEqual(mail.outbox, [])
        parts = {"uid": urlsafe_base64_encode(force_bytes(demo.pk)), "token": default_token_generator.make_token(demo)}
        self.assertEqual(self.reset(parts).status_code, 400)
        demo.refresh_from_db()
        self.assertTrue(demo.check_password("demo1234"))

    def test_google_only_account_can_set_a_password(self):
        user = User.objects.create_user(email="gia@example.com")
        self.assertFalse(user.has_usable_password())
        self.forgot("gia@example.com")
        self.assertEqual(self.reset(self.link_parts()).status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.check_password(NEW_PASSWORD))

    def test_email_limit_is_silent_and_ip_limit_is_not(self):
        email_limit = RESET_LIMITS["reset_email"][0]
        replies = [self.forgot() for _ in range(email_limit + 1)]
        self.assertTrue(all(r.status_code == 200 for r in replies))
        self.assertEqual(len(mail.outbox), email_limit)
        for _ in range(RESET_LIMITS["reset_ip"][0] - email_limit - 1):
            self.forgot("nobody@example.com")
        self.assertEqual(self.forgot("nobody@example.com").status_code, 429)

    def test_mail_failure_still_gives_the_same_reply(self):
        with self.settings(EMAIL_BACKEND="apps.users.tests.BrokenBackend"):
            with self.assertLogs("apps.users.views", level="ERROR"):
                self.assertEqual(self.forgot().json(), {"detail": RESET_SENT})

    @override_settings(EMAIL_HOST="")
    def test_unconfigured_server_says_so(self):
        self.assertEqual(self.forgot().status_code, 503)

    def test_demo_password_cannot_be_changed(self):
        User.objects.create_user(email=DEMO_EMAIL, password="demo1234")
        access = self.client.post(
            "/api/auth/token/", {"email": DEMO_EMAIL, "password": "demo1234"}, format="json"
        ).json()["access"]
        response = self.client.post(
            "/api/auth/password/",
            {"current_password": "demo1234", "new_password": NEW_PASSWORD},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {access}",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], [DEMO_PASSWORD_LOCKED])
        self.assertTrue(User.objects.get(email=DEMO_EMAIL).check_password("demo1234"))
        self.assertEqual(self.me(access).status_code, 200)

    def test_change_password_ends_old_sessions_but_returns_a_new_one(self):
        old = self.sign_in().json()
        response = self.client.post(
            "/api/auth/password/",
            {"current_password": PASSWORD, "new_password": NEW_PASSWORD},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {old['access']}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.me(old["access"]).status_code, 401)
        self.assertEqual(self.me(response.json()["access"]).status_code, 200)


class BrokenBackend:
    def __init__(self, *args, **kwargs):
        pass

    def send_messages(self, messages):
        raise OSError("smtp down")
