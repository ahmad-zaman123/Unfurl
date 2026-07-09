from django.db import models


class Template(models.TextChoices):
    GENERIC = "generic", "Generic"
    ARTICLE = "article", "Article"
    PRODUCT = "product", "Product"
    EVENT = "event", "Event"


class Theme(models.TextChoices):
    BRAND = "brand", "Brand"
    LIGHT = "light", "Light"
    DARK = "dark", "Dark"
