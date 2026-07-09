from django.core.cache import cache

CARD_CACHE_TIMEOUT = 86400
HITS_KEY = "stats:og:hits"
MISSES_KEY = "stats:og:misses"


def _png_key(signature):
    return "card:png:" + signature


def get_cached_png(signature):
    return cache.get(_png_key(signature))


def store_png(signature, png):
    cache.set(_png_key(signature), png, CARD_CACHE_TIMEOUT)


def _bump(name):
    # Counters live for the process/Redis lifetime (best-effort stats).
    if not cache.add(name, 1, timeout=None):
        try:
            cache.incr(name)
        except ValueError:
            cache.add(name, 1, timeout=None)


def record_hit():
    _bump(HITS_KEY)


def record_miss():
    _bump(MISSES_KEY)


def cache_stats():
    hits = cache.get(HITS_KEY, 0)
    misses = cache.get(MISSES_KEY, 0)
    served = hits + misses
    hit_rate = round(hits / served * 100, 1) if served else 0.0
    return {"hits": hits, "misses": misses, "served": served, "hit_rate": hit_rate}
