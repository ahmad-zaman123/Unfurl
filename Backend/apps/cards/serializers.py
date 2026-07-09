import re

from rest_framework import serializers

from apps.cards.choices import Template, Theme
from apps.cards.constants import DEFAULT_ACCENT, MAX_LINE_LEN, MAX_TITLE_LEN

HEX_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
# Strip control characters but keep newlines and tabs (used for manual wrapping).
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class CardSpecSerializer(serializers.Serializer):
    template = serializers.ChoiceField(choices=Template.choices, default=Template.GENERIC)
    theme = serializers.ChoiceField(choices=Theme.choices, default=Theme.BRAND)
    accent = serializers.CharField(default=DEFAULT_ACCENT)

    title = serializers.CharField(max_length=MAX_TITLE_LEN)
    subtitle = serializers.CharField(max_length=MAX_TITLE_LEN, required=False, allow_blank=True)
    eyebrow = serializers.CharField(max_length=MAX_LINE_LEN, required=False, allow_blank=True)
    footer = serializers.CharField(max_length=MAX_LINE_LEN, required=False, allow_blank=True)
    price = serializers.CharField(max_length=MAX_LINE_LEN, required=False, allow_blank=True)
    date = serializers.CharField(max_length=MAX_LINE_LEN, required=False, allow_blank=True)
    location = serializers.CharField(max_length=MAX_LINE_LEN, required=False, allow_blank=True)
    logo = serializers.URLField(max_length=500, required=False, allow_blank=True)

    def validate_accent(self, value):
        if not HEX_COLOR.match(value):
            raise serializers.ValidationError("Accent must be a hex colour like #2563eb.")
        return value

    def validate_logo(self, value):
        if value and not value.startswith(("http://", "https://")):
            raise serializers.ValidationError("Logo must be an http(s) URL.")
        return value

    def validate(self, attrs):
        # Neutralise control characters in every free-text field.
        for field in ("title", "subtitle", "eyebrow", "footer", "price", "date", "location"):
            if field in attrs and attrs[field]:
                attrs[field] = CONTROL_CHARS.sub("", attrs[field])
        return attrs
