import django.core.validators
import django.db.models.deletion
import django.utils.translation
from django.db import migrations, models

import gultix_sponsors.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("pretixbase", "0001_squashed_0028_auto_20160816_1242"),
    ]

    operations = [
        migrations.CreateModel(
            name="SponsorTier",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        max_length=190,
                        verbose_name=django.utils.translation.gettext_lazy("Name"),
                    ),
                ),
                (
                    "position",
                    models.PositiveIntegerField(
                        default=0,
                        verbose_name=django.utils.translation.gettext_lazy("Position"),
                    ),
                ),
                (
                    "logo_width",
                    models.PositiveIntegerField(
                        default=150,
                        help_text=django.utils.translation.gettext_lazy(
                            "Logo width in pixels (40–300)."
                        ),
                        validators=[
                            django.core.validators.MinValueValidator(40),
                            django.core.validators.MaxValueValidator(300),
                        ],
                        verbose_name=django.utils.translation.gettext_lazy(
                            "Logo width"
                        ),
                    ),
                ),
                (
                    "event",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sponsor_tiers",
                        to="pretixbase.Event",
                        verbose_name=django.utils.translation.gettext_lazy("Event"),
                    ),
                ),
            ],
            options={
                "ordering": ("position", "pk"),
                "verbose_name": django.utils.translation.gettext_lazy("Sponsor tier"),
                "verbose_name_plural": django.utils.translation.gettext_lazy(
                    "Sponsor tiers"
                ),
            },
        ),
        migrations.CreateModel(
            name="Sponsor",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        max_length=190,
                        verbose_name=django.utils.translation.gettext_lazy("Name"),
                    ),
                ),
                (
                    "logo",
                    models.ImageField(
                        upload_to=gultix_sponsors.models.sponsor_logo_path,
                        verbose_name=django.utils.translation.gettext_lazy("Logo"),
                    ),
                ),
                (
                    "website",
                    models.URLField(
                        blank=True,
                        help_text=django.utils.translation.gettext_lazy(
                            "Optional, HTTPS only."
                        ),
                        validators=[gultix_sponsors.models.validate_https_url],
                        verbose_name=django.utils.translation.gettext_lazy("Website"),
                    ),
                ),
                (
                    "position",
                    models.PositiveIntegerField(
                        default=0,
                        verbose_name=django.utils.translation.gettext_lazy("Position"),
                    ),
                ),
                (
                    "published",
                    models.BooleanField(
                        default=False,
                        verbose_name=django.utils.translation.gettext_lazy("Published"),
                    ),
                ),
                (
                    "tier",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sponsors",
                        to="gultix_sponsors.sponsortier",
                        verbose_name=django.utils.translation.gettext_lazy("Tier"),
                    ),
                ),
            ],
            options={
                "ordering": ("position", "pk"),
                "verbose_name": django.utils.translation.gettext_lazy("Sponsor"),
                "verbose_name_plural": django.utils.translation.gettext_lazy(
                    "Sponsors"
                ),
            },
        ),
    ]
