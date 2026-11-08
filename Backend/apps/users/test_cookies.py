from django.test import TestCase
from rest_framework.test import APIClient

from apps.users.models import User

SAME = {"HTTP_SEC_FETCH_SITE": "same-origin"}
CROSS = {"HTTP_SEC_FETCH_SITE": "cross-site"}


class SessionCookieTests(TestCase):
    def setUp(self):
        User.objects.create_user(email="sara@example.com", password="first-password-1")
        self.client = APIClient()

    def sign_in(self):
        return self.client.post("/api/auth/token/", {"email": "sara@example.com", "password": "first-password-1"}, format="json", **SAME)

    def test_sign_in_sets_httponly_cookies_and_the_body_has_no_tokens(self):
        response = self.sign_in()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {})
        access, refresh = response.cookies["access_token"], response.cookies["refresh_token"]
        for cookie in (access, refresh):
            self.assertTrue(cookie["httponly"])
            self.assertTrue(cookie["secure"])
            self.assertEqual(cookie["samesite"], "Lax")
        self.assertEqual((access["path"], refresh["path"]), ("/api/", "/api/auth/"))

    def test_the_cookie_signs_requests_in(self):
        self.sign_in()
        self.assertEqual(self.client.get("/api/auth/me/").json()["email"], "sara@example.com")

    def test_a_write_from_another_site_does_not_count_the_cookie(self):
        self.sign_in()
        self.assertEqual(self.client.post("/api/auth/password/", {}, format="json", **CROSS).status_code, 401)
        self.assertEqual(self.client.post("/api/auth/password/", {}, format="json", HTTP_ORIGIN="https://evil.example").status_code, 401)
        self.assertEqual(self.client.post("/api/auth/password/", {}, format="json").status_code, 401)
        self.assertEqual(self.client.post("/api/auth/password/", {}, format="json", **SAME).status_code, 400)

    def test_refresh_uses_the_cookie_and_keeps_the_new_token_out_of_the_body(self):
        self.sign_in()
        old = self.client.cookies["access_token"].value
        refreshed = self.client.post("/api/auth/token/refresh/", **SAME)
        self.assertEqual(refreshed.status_code, 200)
        self.assertEqual(refreshed.json(), {})
        self.assertIn("access_token", refreshed.cookies)
        self.assertNotEqual(refreshed.cookies["access_token"].value, "")
        self.assertTrue(old)
        self.assertEqual(self.client.post("/api/auth/token/refresh/", **CROSS).status_code, 401)

    def test_an_expired_cookie_counts_as_signed_out(self):
        self.client.cookies["access_token"] = "not-a-real-token"
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)
        self.assertEqual(self.sign_in().status_code, 200)

    def test_logout_clears_both_cookies(self):
        self.sign_in()
        response = self.client.post("/api/auth/logout/", **SAME)
        self.assertEqual(response.status_code, 204)
        for name in ("access_token", "refresh_token"):
            self.assertEqual(response.cookies[name].value, "")
            self.assertEqual(response.cookies[name]["max-age"], 0)
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 401)
