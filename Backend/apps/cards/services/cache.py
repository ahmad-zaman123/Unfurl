import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

CARD_CACHE_TIMEOUT = 86400
HITS_KEY = "stats:og:hits"
MISSES_KEY = "stats:og:misses"

# Everything here is an optimisation or a best-effort statistic. If the cache backend is
# unreachable (a paused Redis, a bad REDIS_URL), a card must still be rendered and served
# and the usage page must still load, so each call degrades instead of raising.


def _png_key(signature):
    return "card:png:" + signature


def get_cached_png(signature):
    try:
        return cache.get(_png_key(signature))
    except Exception:
        logger.warning("Card cache unavailable (get); rendering uncached.", exc_info=True)
        return None


def store_png(signature, png):
    try:
        cache.set(_png_key(signature), png, CARD_CACHE_TIMEOUT)
    except Exception:
        logger.warning("Card cache unavailable (set); card not cached.", exc_info=True)


def _bump(name):
    # Counters live for the process/Redis lifetime (best-effort stats).
    try:
        if not cache.add(name, 1, timeout=None):
            try:
                cache.incr(name)
            except ValueError:
                cache.add(name, 1, timeout=None)
    except Exception:
        logger.warning("Card cache unavailable (stats).", exc_info=True)


def record_hit():
    _bump(HITS_KEY)


def record_miss():
    _bump(MISSES_KEY)


def cache_stats():
    try:
        hits = cache.get(HITS_KEY, 0)
        misses = cache.get(MISSES_KEY, 0)
    except Exception:
        logger.warning("Card cache unavailable (stats read).", exc_info=True)
        return {"hits": 0, "misses": 0, "served": 0, "hit_rate": 0.0}
    served = hits + misses
    hit_rate = round(hits / served * 100, 1) if served else 0.0
    return {"hits": hits, "misses": misses, "served": served, "hit_rate": hit_rate}
