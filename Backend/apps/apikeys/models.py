import hashlib
import secrets

from django.db import models
from django.db.models import F
from django.utils import timezone

from apps.apikeys.constants import KEY_DISPLAY_LEN, KEY_ENVIRONMENT, KEY_PREFIX
from apps.core.models import BaseModel


def hash_key(raw_key):
    return hashlib.sha256(raw_key.encode()).hexdigest()


class ApiKey(BaseModel):
    name = models.CharField(max_length=255)
    prefix = models.CharField(max_length=16)
    hashed_key = models.CharField(max_length=64, unique=True, db_index=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    owner = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="api_keys",
    )

    class Meta:
        verbose_name = "API key"
        verbose_name_plural = "API keys"
        db_table = "api_keys"
        ordering = ("-created",)

    @property
    def is_active(self):
        return self.revoked_at is None

    @classmethod
    def generate(cls, *, owner, name):
        """Create a key and return (instance, raw_key). The raw key is shown once."""
        raw_key = KEY_PREFIX + KEY_ENVIRONMENT + secrets.token_urlsafe(24)
        instance = cls.objects.create(
            owner=owner,
            name=name,
            prefix=raw_key[:KEY_DISPLAY_LEN],
            hashed_key=hash_key(raw_key),
        )
        return instance, raw_key

    def __str__(self):
        return self.name + " (" + self.prefix + "…)"


class KeyUsageDay(BaseModel):
    date = models.DateField()
    count = models.PositiveIntegerField(default=0)

    api_key = models.ForeignKey(
        "apikeys.ApiKey",
        on_delete=models.CASCADE,
        related_name="usage_days",
    )
    owner = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="usage_days",
    )

    class Meta:
        verbose_name = "key usage day"
        verbose_name_plural = "key usage days"
        db_table = "key_usage_days"
        ordering = ("-date",)
        constraints = (
            models.UniqueConstraint(fields=("api_key", "date"), name="uniq_key_usage_day"),
        )
        indexes = (models.Index(fields=("owner", "date"), name="idx_usage_owner_date"),)

    @classmethod
    def record(cls, api_key):
        """Atomically increment today's usage count for an API key."""
        today = timezone.now().date()
        row, _ = cls.objects.get_or_create(
            api_key=api_key,
            date=today,
            defaults={"owner_id": api_key.owner_id},
        )
        cls.objects.filter(pk=row.pk).update(count=F("count") + 1)

    def __str__(self):
        return self.api_key.prefix + " " + str(self.date) + ": " + str(self.count)
