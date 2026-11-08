"""Sign-in tokens live in httpOnly cookies, which page scripts can't read.

Every endpoint that hands out tokens still builds the usual {"access", "refresh"} reply. TokenCookieMiddleware moves
those two values into cookies on the way out, so no reply body carries a token. CookieJWTAuthentication reads the
access cookie, and only trusts it for a write when the browser says the request came from this site.
"""

import json

from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
# The refresh cookie is only sent to the auth endpoints, the access cookie to the whole API.
ACCESS_PATH = "/api/"
REFRESH_PATH = "/api/auth/"
SAFE_METHODS = ("GET", "HEAD", "OPTIONS")


def _cookie_options(path):
    return {"httponly": True, "secure": not settings.DEBUG, "samesite": "Lax", "path": path}


def set_auth_cookies(response, access=None, refresh=None):
    lifetimes = settings.SIMPLE_JWT
    if access:
        age = int(lifetimes["ACCESS_TOKEN_LIFETIME"].total_seconds())
        response.set_cookie(ACCESS_COOKIE, access, max_age=age, **_cookie_options(ACCESS_PATH))
    if refresh:
        age = int(lifetimes["REFRESH_TOKEN_LIFETIME"].total_seconds())
        response.set_cookie(REFRESH_COOKIE, refresh, max_age=age, **_cookie_options(REFRESH_PATH))


def clear_auth_cookies(response):
    response.delete_cookie(ACCESS_COOKIE, path=ACCESS_PATH, samesite="Lax")
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH, samesite="Lax")


def from_this_site(request):
    """True when the browser says the request came from the app's own pages."""
    fetch_site = request.headers.get("Sec-Fetch-Site")
    if fetch_site:
        return fetch_site == "same-origin"
    origin = request.headers.get("Origin")
    return bool(origin) and origin in getattr(settings, "CORS_ALLOWED_ORIGINS", [])


class TokenCookieMiddleware:
    """Moves "access" and "refresh" out of auth replies and into httpOnly cookies."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not request.path.startswith(REFRESH_PATH) or not 200 <= response.status_code < 300:
            return response
        if "application/json" not in response.get("Content-Type", ""):
            return response
        try:
            data = json.loads(response.content or b"null")
        except ValueError:
            return response
        if not isinstance(data, dict) or not ({"access", "refresh"} & data.keys()):
            return response
        set_auth_cookies(response, data.pop("access", None), data.pop("refresh", None))
        response.content = json.dumps(data)
        response["Content-Length"] = str(len(response.content))
        return response


class CookieJWTAuthentication(JWTAuthentication):
    """An Authorization header still works for scripts. Browsers use the access cookie."""

    def authenticate(self, request):
        if self.get_header(request) is not None:
            return super().authenticate(request)
        raw = request.COOKIES.get(ACCESS_COOKIE)
        if not raw:
            return None
        if request.method not in SAFE_METHODS and not from_this_site(request):
            return None
        try:
            validated = self.get_validated_token(raw.encode())
        except InvalidToken:
            # An expired cookie counts as signed out, so sign-in and refresh still work and other endpoints say 401.
            return None
        return self.get_user(validated), validated
