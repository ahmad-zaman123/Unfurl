from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class BillingAccount(BaseModel):
    """Links a user to their Stripe customer. User.plan stays what the rate limiter reads."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="billing")
    stripe_customer_id = models.CharField(max_length=255, unique=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=32, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancels_at = models.DateTimeField(null=True, blank=True)
    checkout_session_id = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "billing_accounts"

    def __str__(self):
        return self.stripe_customer_id
