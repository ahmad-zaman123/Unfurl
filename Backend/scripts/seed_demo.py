"""Seed a demo account for recruiters. Run with:  python scripts/seed_demo.py"""
import os
import sys
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

import django

django.setup()

from django.utils import timezone

from apps.apikeys.models import ApiKey, KeyUsageDay
from apps.users.models import User

DEMO_EMAIL = "demo@unfurl.app"
DEMO_PASSWORD = "demo1234"

# Idempotent: rebuild the demo account from scratch.
User.objects.filter(email=DEMO_EMAIL).delete()
user = User.objects.create_user(email=DEMO_EMAIL, password=DEMO_PASSWORD, full_name="Demo User")
print("user:", user.email)

production, _ = ApiKey.generate(owner=user, name="Production")
staging, _ = ApiKey.generate(owner=user, name="Staging")
print("keys:", production.name, staging.name)

today = timezone.now().date()
counts = [4, 9, 6, 14, 11, 18, 13, 10, 24, 17, 21, 12, 8, 6]
for index, count in enumerate(counts):
    day = today - timedelta(days=len(counts) - 1 - index)
    key = production if index % 3 else staging
    KeyUsageDay.objects.update_or_create(
        api_key=key,
        date=day,
        defaults={"owner_id": user.id, "count": count},
    )
print("seeded", len(counts), "days of usage")
print("=== demo seeded ===")
