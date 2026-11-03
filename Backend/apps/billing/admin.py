from django.contrib import admin

from apps.billing.models import BillingAccount


@admin.register(BillingAccount)
class BillingAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "current_period_end", "cancels_at")
    search_fields = ("user__email", "stripe_customer_id", "stripe_subscription_id")
    readonly_fields = ("stripe_customer_id", "stripe_subscription_id", "status", "current_period_end", "cancels_at")
