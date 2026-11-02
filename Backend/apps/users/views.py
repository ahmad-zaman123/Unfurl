import logging

from django.conf import settings
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.apikeys.ratelimit import check_window
from apps.users.constants import DEMO_EMAIL, RESET_LIMITS, RESET_SENT, RESET_TOO_MANY
from apps.users.emails import send_password_reset_email
from apps.users.models import User
from apps.users.serializers import (
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
    UserSerializer,
)

logger = logging.getLogger(__name__)


def client_ip(request):
    return request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR") or "unknown"


def within_limit(scope, identifier):
    limit, window = RESET_LIMITS[scope]
    return check_window(identifier, scope, limit, window).allowed


class RegisterAPIView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = (AllowAny,)


class MeAPIView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        return self.request.user


class GoogleAuthAPIView(APIView):
    """Sign in (or sign up) with a Google ID token from Google Identity Services.

    The frontend's "Continue with Google" button hands us the credential; we verify it
    against Google's public keys and the configured client id, then issue the same JWT
    pair the password login does. New emails get an account with no usable password.
    """

    permission_classes = (AllowAny,)
    authentication_classes = ()

    def post(self, request):
        client_id = getattr(settings, "GOOGLE_CLIENT_ID", "")
        if not client_id:
            return Response(
                {"detail": "Google sign-in is not configured on this server."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        credential = request.data.get("credential")
        if not credential or not isinstance(credential, str):
            return Response({"detail": "Missing Google credential."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            claims = google_id_token.verify_oauth2_token(credential, google_requests.Request(), client_id)
        except ValueError:
            return Response(
                {"detail": "Google sign-in could not be verified. Try again."}, status=status.HTTP_400_BAD_REQUEST
            )
        email = (claims.get("email") or "").lower()
        if not email or not claims.get("email_verified"):
            return Response({"detail": "Google did not return a verified email."}, status=status.HTTP_400_BAD_REQUEST)

        user, created = User.objects.get_or_create(email=email, defaults={"full_name": claims.get("name") or ""})
        if created:
            user.set_unusable_password()
            user.save(update_fields=["password"])
        if not user.is_active:
            return Response({"detail": "This account is disabled."}, status=status.HTTP_403_FORBIDDEN)

        refresh = RefreshToken.for_user(user)
        return Response({"access": str(refresh.access_token), "refresh": str(refresh), "created": created})


class ChangePasswordAPIView(APIView):
    """Change (or, for Google sign-in accounts, first set) the signed-in user's password.

    Changing it ends every existing session, so this one gets a fresh JWT pair.
    """

    permission_classes = (IsAuthenticated,)

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        refresh = RefreshToken.for_user(serializer.save())
        return Response({"detail": "Password changed.", "access": str(refresh.access_token), "refresh": str(refresh)})


class ForgotPasswordAPIView(APIView):
    """Email a reset link. The reply is the same whether or not the address has an account."""

    permission_classes = (AllowAny,)
    authentication_classes = ()

    def post(self, request):
        if not settings.EMAIL_HOST:
            return Response(
                {"detail": "Password reset isn't available right now."}, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not (within_limit("reset_ip", client_ip(request)) and within_limit("reset_all", "all")):
            return Response({"detail": RESET_TOO_MANY}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        email = serializer.validated_data["email"].lower()
        # Over this limit nothing is sent, but the reply stays the same for every address.
        if email != DEMO_EMAIL and within_limit("reset_email", email):
            for user in User.objects.filter(email__iexact=email, is_active=True):
                try:
                    send_password_reset_email(user)
                except Exception:
                    logger.exception("Could not send a password reset email")
        return Response({"detail": RESET_SENT})


class ResetPasswordAPIView(APIView):
    """Set a new password from an emailed link, which also ends the account's existing sessions."""

    permission_classes = (AllowAny,)
    authentication_classes = ()

    def post(self, request):
        if not within_limit("reset_use", client_ip(request)):
            return Response({"detail": RESET_TOO_MANY}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Password changed."})
