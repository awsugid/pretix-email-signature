import os
import uuid
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from urllib.parse import urlparse

LOGO_WIDTH_MIN = 40
LOGO_WIDTH_MAX = 300
LOGO_WIDTH_DEFAULT = 150
LOGO_EXTENSIONS = ("png", "jpg", "jpeg")


def sponsor_logo_path(instance, filename: str) -> str:
    """Unguessable public path. New upload = new path, old files are preserved."""
    ext = os.path.splitext(filename)[1].lstrip(".").lower()
    if ext not in LOGO_EXTENSIONS:
        ext = "png"
    return "pub/gultix-sponsors/{}.{}".format(uuid.uuid4().hex, ext)


def validate_https_url(value):
    if urlparse(value).scheme != "https":
        raise ValidationError(
            "Enter a valid HTTPS URL (starting with https://).",
            code="invalid_scheme",
        )


class SponsorTier(models.Model):
    event = models.ForeignKey(
        "pretixbase.Event",
        on_delete=models.CASCADE,
        related_name="sponsor_tiers",
        verbose_name=_("Event"),
    )
    name = models.CharField(max_length=190, verbose_name=_("Name"))
    position = models.PositiveIntegerField(default=0, verbose_name=_("Position"))
    logo_width = models.PositiveIntegerField(
        default=LOGO_WIDTH_DEFAULT,
        validators=[
            MinValueValidator(LOGO_WIDTH_MIN),
            MaxValueValidator(LOGO_WIDTH_MAX),
        ],
        verbose_name=_("Logo width"),
        help_text=_("Logo width in pixels (%(min)s–%(max)s).")
        % {"min": LOGO_WIDTH_MIN, "max": LOGO_WIDTH_MAX},
    )

    class Meta:
        ordering = ("position", "pk")
        verbose_name = _("Sponsor tier")
        verbose_name_plural = _("Sponsor tiers")

    def __str__(self):
        return self.name


class Sponsor(models.Model):
    tier = models.ForeignKey(
        SponsorTier,
        on_delete=models.CASCADE,
        related_name="sponsors",
        verbose_name=_("Tier"),
    )
    name = models.CharField(max_length=190, verbose_name=_("Name"))
    logo = models.ImageField(upload_to=sponsor_logo_path, verbose_name=_("Logo"))
    website = models.URLField(
        blank=True,
        validators=[validate_https_url],
        verbose_name=_("Website"),
        help_text=_("Optional, HTTPS only."),
    )
    position = models.PositiveIntegerField(default=0, verbose_name=_("Position"))
    published = models.BooleanField(default=False, verbose_name=_("Published"))

    class Meta:
        ordering = ("position", "pk")
        verbose_name = _("Sponsor")
        verbose_name_plural = _("Sponsors")

    def __str__(self):
        return self.name
