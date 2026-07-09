from django.utils import timezone
from rest_framework import authentication, exceptions

from apps.apikeys.constants import KEY_PREFIX
from apps.apikeys.models import ApiKey, hash_key


class ApiKeyAuthentication(authentication.BaseAuthentication):
    """Authenticate `Authorization: Bearer sk_...` requests against hashed keys.

    Returns None for non-key Bearer tokens (e.g. JWTs) so that other
    authentication classes further down the list can handle them.
    """

    keyword = b"bearer"

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).split()
        if len(header) != 2 or header[0].lower() != self.keyword:
            return None

        token = header[1].decode()
        if not token.startswith(KEY_PREFIX):
            return None

        try:
            key = ApiKey.objects.select_related("owner").get(hashed_key=hash_key(token))
        except ApiKey.DoesNotExist:
            raise exceptions.AuthenticationFailed("Invalid API key.")

        if key.revoked_at is not None:
            raise exceptions.AuthenticationFailed("This API key has been revoked.")

        ApiKey.objects.filter(pk=key.pk).update(last_used_at=timezone.now())
        return (key.owner, key)

    def authenticate_header(self, request):
        # Advertising a scheme makes DRF return 401 (not 403) on auth failure.
        return "Bearer"
