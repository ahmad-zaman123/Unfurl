DEMO_EMAIL = "demo@unfurl.app"
DEMO_PASSWORD_LOCKED = "The demo account is shared, so its password can't be changed."

RESET_SENT = "If that email has an account, we've sent a reset link."
RESET_INVALID = "This reset link is invalid or has expired."
RESET_TOO_MANY = "Too many attempts. Please try again later."

# (limit, window in seconds). The Gmail account is shared between apps and allows about
# 500 emails a day, so this app keeps its own daily total well under that.
RESET_LIMITS = {
    "reset_ip": (10, 3600),
    "reset_email": (3, 3600),
    "reset_all": (100, 86400),
    "reset_use": (20, 3600),
}
