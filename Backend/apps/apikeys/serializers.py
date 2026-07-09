from rest_framework import serializers

from apps.apikeys.models import ApiKey


class ApiKeySerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = ApiKey
        fields = ("id", "name", "prefix", "is_active", "last_used_at", "revoked_at", "created")
        read_only_fields = fields


class ApiKeyCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApiKey
        fields = ("name",)
