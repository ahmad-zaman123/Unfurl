"""The refresh and sign-out endpoints for cookie sessions (see cookies.py)."""

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.views import TokenRefreshView

from apps.users.cookies import REFRESH_COOKIE, clear_auth_cookies, from_this_site


class CookieTokenRefreshView(TokenRefreshView):
    """Takes the refresh token from its cookie when the body doesn't carry one."""

    def post(self, request, *args, **kwargs):
        refresh = request.data.get("refresh") if hasattr(request.data, "get") else None
        if not refresh and not from_this_site(request):
            return Response({"detail": "Sign in again."}, status=status.HTTP_401_UNAUTHORIZED)
        serializer = self.get_serializer(data={"refresh": refresh or request.COOKIES.get(REFRESH_COOKIE, "")})
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            raise InvalidToken(exc.args[0]) from exc
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class LogoutAPIView(APIView):
    """Clears the session cookies."""

    authentication_classes = ()
    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        response = Response(status=status.HTTP_204_NO_CONTENT)
        clear_auth_cookies(response)
        return response
