from django.urls import path

from apps.cards.views import CardCreateAPIView, OGImageAPIView

urlpatterns = [
    path("v1/cards", CardCreateAPIView.as_view(), name="card-create"),
    path("v1/og", OGImageAPIView.as_view(), name="og-image"),
]
