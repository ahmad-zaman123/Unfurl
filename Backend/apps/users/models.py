from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from apps.core.models import BaseModel
from apps.users.choices import Plan
from apps.users.managers import UserManager


class User(AbstractBaseUser, PermissionsMixin, BaseModel):
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255, blank=True)
    plan = models.CharField(max_length=16, choices=Plan.choices, default=Plan.FREE)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ()

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"
        db_table = "users"

    def __str__(self):
        return self.email
