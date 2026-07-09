import hashlib
import hmac

from django.conf import settings


def _secret():
    return getattr(settings, "CARD_SIGNING_SECRET", settings.SECRET_KEY).encode()


def _canonical(params):
    # Deterministic string over the (non-signature) params, sorted by key.
    return "&".join(key + "=" + str(params[key]) for key in sorted(params))


def sign(params):
    return hmac.new(_secret(), _canonical(params).encode(), hashlib.sha256).hexdigest()


def verify(params, signature):
    return hmac.compare_digest(sign(params), signature or "")
