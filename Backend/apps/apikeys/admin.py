from django.contrib import admin

from apps.apikeys.models import ApiKey


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ("name", "prefix", "owner", "is_active", "last_used_at", "created")
    search_fields = ("name", "prefix", "owner__email")
    readonly_fields = ("prefix", "hashed_key", "last_used_at")
    ordering = ("-created",)
