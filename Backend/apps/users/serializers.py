from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers

from apps.users.constants import DEMO_PASSWORD_LOCKED, RESET_INVALID
from apps.users.demo import is_demo_user
from apps.users.models import User


class UserSerializer(serializers.ModelSerializer):
    # False for accounts created through Google sign-in that never set one.
    has_password = serializers.SerializerMethodField()
    # Lets the header show "Demo account" instead of the profile menu.
    is_demo = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "email", "full_name", "plan", "has_password", "is_demo")
        read_only_fields = fields

    def get_has_password(self, obj):
        return obj.has_usable_password()

    def get_is_demo(self, obj):
        return is_demo_user(obj)


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ("id", "email", "full_name", "password")
        read_only_fields = ("id",)

    def create(self, validated_data):
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, **validated_data)


class ChangePasswordSerializer(serializers.Serializer):
    """Set a new password. The current one is required unless the account has none yet
    (Google sign-in accounts), in which case this simply adds one."""

    current_password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        user = self.context["request"].user
        if is_demo_user(user):
            raise serializers.ValidationError({"detail": DEMO_PASSWORD_LOCKED})
        current = attrs.get("current_password") or ""
        if user.has_usable_password() and not (current and user.check_password(current)):
            raise serializers.ValidationError({"current_password": "Your current password is wrong."})
        if current and current == attrs["new_password"]:
            raise serializers.ValidationError(
                {"new_password": "Choose something different from your current password."}
            )
        try:
            validate_password(attrs["new_password"], user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)}) from exc
        return attrs

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    """Set a new password from an emailed link. The token is tied to the current password,
    so it stops working as soon as the password changes."""

    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        try:
            user = User.objects.filter(pk=urlsafe_base64_decode(attrs["uid"]).decode(), is_active=True).first()
        except (TypeError, ValueError, OverflowError, DjangoValidationError):
            user = None
        if user is None or is_demo_user(user) or not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError({"detail": RESET_INVALID})
        try:
            validate_password(attrs["new_password"], user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)}) from exc
        attrs["user"] = user
        return attrs

    def save(self, **kwargs):
        user = self.validated_data["user"]
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user
