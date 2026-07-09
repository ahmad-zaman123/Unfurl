import time
from dataclasses import dataclass
from datetime import date

from django.core.cache import cache
from django.db.models import Sum

from apps.apikeys.constants import DEFAULT_PLAN, PLAN_LIMITS


@dataclass
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset: int
    retry_after: int


def _check_window(identifier, scope, limit, window_seconds):
    """Fixed-window counter backed by an atomic cache incr."""
    now = int(time.time())
    window_start = now - (now % window_seconds)
    reset = window_start + window_seconds
    cache_key = "rl:%s:%s:%s" % (scope, identifier, window_start)

    cache.add(cache_key, 0, timeout=window_seconds + 1)
    try:
        count = cache.incr(cache_key)
    except ValueError:
        # The key expired between add and incr; start the window again.
        cache.add(cache_key, 0, timeout=window_seconds + 1)
        count = cache.incr(cache_key)

    allowed = count <= limit
    remaining = max(0, limit - count)
    retry_after = max(1, reset - now) if not allowed else 0
    return RateLimitResult(allowed, limit, remaining, reset, retry_after)


def plan_limits(plan):
    return PLAN_LIMITS.get(plan, PLAN_LIMITS[DEFAULT_PLAN])


def check_api_key_limits(api_key):
    """Enforce the per-minute and per-day windows for one API key, by plan."""
    limits = plan_limits(api_key.owner.plan)
    minute = _check_window(api_key.pk, "min", limits["per_minute"], 60)
    day = _check_window(api_key.pk, "day", limits["per_day"], 86400)
    if not minute.allowed:
        return minute
    if not day.allowed:
        return day
    return minute


def monthly_usage(user):
    from apps.apikeys.models import KeyUsageDay

    month_start = date.today().replace(day=1)
    used = KeyUsageDay.objects.filter(owner=user, date__gte=month_start).aggregate(
        total=Sum("count")
    )["total"]
    return used or 0


def monthly_quota(user):
    return plan_limits(user.plan)["per_month"]


def apply_headers(response, result):
    response["X-RateLimit-Limit"] = str(result.limit)
    response["X-RateLimit-Remaining"] = str(result.remaining)
    response["X-RateLimit-Reset"] = str(result.reset)
    if not result.allowed:
        response["Retry-After"] = str(result.retry_after)
    return response
