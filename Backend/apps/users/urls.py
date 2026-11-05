from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.users.views import (
    ChangePasswordAPIView,
    DemoAPIView,
    ForgotPasswordAPIView,
    GoogleAuthAPIView,
    MeAPIView,
    RegisterAPIView,
    ResetPasswordAPIView,
)

urlpatterns = [
    path("auth/register/", RegisterAPIView.as_view(), name="register"),
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/demo/", DemoAPIView.as_view(), name="demo"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/me/", MeAPIView.as_view(), name="me"),
    path("auth/google/", GoogleAuthAPIView.as_view(), name="google"),
    path("auth/password/", ChangePasswordAPIView.as_view(), name="password"),
    path("auth/password/forgot/", ForgotPasswordAPIView.as_view(), name="password_forgot"),
    path("auth/password/reset/", ResetPasswordAPIView.as_view(), name="password_reset"),
]
