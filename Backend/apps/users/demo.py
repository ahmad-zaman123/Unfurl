"""Private demo accounts.

Each visitor who clicks "Try the live demo" gets a fresh account with two API keys and two weeks
of usage, so the dashboard has something to show and nobody sees anyone else's keys.
"""

import uuid
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.apikeys.models import ApiKey, KeyUsageDay
from apps.users.constants import DEMO_EMAIL
from apps.users.models import User

DEMO_DOMAIN = "demo.unfurl.app"
DEMO_LIFETIME = timedelta(days=2)
PURGE_BATCH = 50

# Requests per day for the last two weeks, oldest first.
USAGE = [4, 9, 6, 14, 11, 18, 13, 10, 24, 17, 21, 12, 8, 6]


def is_demo_email(email):
    email = (email or "").lower()
    return email == DEMO_EMAIL or email.endswith("@" + DEMO_DOMAIN)


def is_demo_user(user):
    return is_demo_email(getattr(user, "email", ""))


def seed_demo_data(user):
    """Give `user` a Production and a Staging key with two weeks of usage. Returns the keys."""
    production, _ = ApiKey.generate(owner=user, name="Production")
    staging, _ = ApiKey.generate(owner=user, name="Staging")
    today = timezone.now().date()
    KeyUsageDay.objects.bulk_create(
        KeyUsageDay(
            api_key=production if index % 3 else staging,
            owner=user,
            date=today - timedelta(days=len(USAGE) - 1 - index),
            count=count,
        )
        for index, count in enumerate(USAGE)
    )
    return production, staging


def purge_expired_demos():
    """Delete a batch of demo accounts older than DEMO_LIFETIME (their keys and usage go with them)."""
    cutoff = timezone.now() - DEMO_LIFETIME
    ids = list(
        User.objects.filter(email__endswith="@" + DEMO_DOMAIN, created__lt=cutoff)
        .order_by("created")
        .values_list("id", flat=True)[:PURGE_BATCH]
    )
    if ids:
        User.objects.filter(id__in=ids).delete()


def create_demo_user():
    purge_expired_demos()
    with transaction.atomic():
        user = User(email=f"demo-{uuid.uuid4().hex[:12]}@{DEMO_DOMAIN}", full_name="Demo User")
        user.set_unusable_password()
        user.save()
        seed_demo_data(user)
    return user
