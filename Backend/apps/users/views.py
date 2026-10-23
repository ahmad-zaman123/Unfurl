from django.conf import settings
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.models import User
from apps.users.serializers import RegisterSerializer, UserSerializer


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
