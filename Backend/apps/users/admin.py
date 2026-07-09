from django.contrib import admin

from apps.users.models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "full_name", "is_staff", "is_active", "created")
    search_fields = ("email", "full_name")
    ordering = ("-created",)
