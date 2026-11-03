PRO_PRICE_LABEL = "$19/month"

# Stripe keeps retrying a failed renewal while it's past_due, so the customer stays
# on Pro until Stripe gives up and the status moves on.
PRO_STATUSES = ("active", "trialing", "past_due")

# Webhooks only say something changed. The current state is always read back from Stripe,
# so duplicates and events that arrive out of order can't leave the wrong plan behind.
SYNC_EVENTS = (
    "checkout.session.completed",
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
)

# Each checkout or portal request calls Stripe several times: (requests, seconds).
SESSION_LIMIT = (10, 60)

BILLING_OFF = "Billing isn't available right now."
BILLING_FAILED = "We couldn't reach the payment provider. Please try again."
BILLING_TOO_MANY = "Too many billing requests. Please wait a minute and try again."
DEMO_BILLING_LOCKED = "The demo account is shared, so it can't be upgraded. Create a free account to try this."
ALREADY_PRO = "You're already on Pro. Use Manage billing to change your subscription."
NO_SUBSCRIPTION = "You don't have a subscription to manage yet."
