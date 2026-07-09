from django.urls import path

from apps.apikeys.views import ApiKeyListCreateAPIView, ApiKeyRevokeAPIView, UsageAPIView

urlpatterns = [
    path("keys/", ApiKeyListCreateAPIView.as_view(), name="apikey-list"),
    path("keys/<uuid:pk>/", ApiKeyRevokeAPIView.as_view(), name="apikey-revoke"),
    path("usage/", UsageAPIView.as_view(), name="usage"),
]
