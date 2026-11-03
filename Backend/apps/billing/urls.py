from django.urls import path

from apps.billing.views import BillingAPIView, CheckoutAPIView, PortalAPIView, StripeWebhookAPIView

urlpatterns = [
    path("billing/", BillingAPIView.as_view(), name="billing"),
    path("billing/checkout/", CheckoutAPIView.as_view(), name="billing-checkout"),
    path("billing/portal/", PortalAPIView.as_view(), name="billing-portal"),
    path("billing/webhook/", StripeWebhookAPIView.as_view(), name="billing-webhook"),
]
