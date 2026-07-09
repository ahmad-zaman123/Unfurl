# All issued keys carry this prefix so the authentication class can tell an
# API key apart from a JWT (both arrive as "Authorization: Bearer ...").
KEY_PREFIX = "sk_"
KEY_ENVIRONMENT = "live_"
KEY_DISPLAY_LEN = 12

# Per-plan limits: per-minute + per-day are enforced per key; per-month is an
# account-wide quota summed across all of a user's keys.
DEFAULT_PLAN = "free"
PLAN_LIMITS = {
    "free": {"per_minute": 60, "per_day": 5000, "per_month": 50000},
    "pro": {"per_minute": 600, "per_day": 100000, "per_month": 2000000},
}
