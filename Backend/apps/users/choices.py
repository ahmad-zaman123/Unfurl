from django.db import models


class Plan(models.TextChoices):
    FREE = "free", "Free"
    PRO = "pro", "Pro"
