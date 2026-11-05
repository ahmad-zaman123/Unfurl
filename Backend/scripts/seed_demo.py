"""Seed a shared demo account for local development. Run with:  python scripts/seed_demo.py"""
import os
import sys
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

import django

django.setup()

from apps.users.demo import seed_demo_data
from apps.users.models import User

DEMO_EMAIL = "demo@unfurl.app"
DEMO_PASSWORD = "demo1234"

# Idempotent: rebuild the shared local demo account from scratch. The live site gives each
# visitor a private demo instead (POST /api/auth/demo/).
User.objects.filter(email=DEMO_EMAIL).delete()
user = User.objects.create_user(email=DEMO_EMAIL, password=DEMO_PASSWORD, full_name="Demo User")
production, staging = seed_demo_data(user)
print("user:", user.email)
print("keys:", production.name, staging.name)
print("=== demo seeded ===")
