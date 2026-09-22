from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import (
    LOGO_WIDTH_MAX,
    LOGO_WIDTH_MIN,
    Sponsor,
    SponsorTier,
    validate_https_url,
)

# 2 MiB: below Django's default DATA_UPLOAD_MAX_MEMORY_SIZE (2.5 MiB) so a
# rejected logo never kills the whole request body before form validation.
MAX_LOGO_UPLOAD_SIZE = 2 * 1024 * 1024
LOGO_FORMATS = ("PNG", "JPEG")
LOGO_WIDTH_PRESETS = (
    ("100", _("Small (100 px)")),
    ("150", _("Medium (150 px)")),
    ("200", _("Large (200 px)")),
)
CUSTOM_LOGO_WIDTH = "custom"


class LogoImageField(forms.ImageField):
    """Image upload restricted to PNG/JPEG with real decoding and a size cap.

    FileInput instead of ClearableFileInput: a cleared logo would break the
    email renderer (missing logo.url), so clearing is never offered nor
    honored; a forged "logo-clear" POST key is ignored and the existing
    logo stays.
    """

    widget = forms.FileInput

    default_error_messages = {
        "invalid_image_format": _("Upload a PNG or JPEG image."),
        "too_large": _("Logo file too large (maximum 2 MB)."),
    }

    def to_python(self, data):
        # Size check first: never hand oversized files to Pillow for decoding.
        if hasattr(data, "size") and data.size > MAX_LOGO_UPLOAD_SIZE:
            raise ValidationError(
                self.error_messages["too_large"],
                code="too_large",
            )
        f = super().to_python(data)
        if f is None:
            return None
        image = getattr(f, "image", None)
        if image is not None and image.format not in LOGO_FORMATS:
            raise forms.ValidationError(
                self.error_messages["invalid_image_format"],
                code="invalid_image_format",
            )
        return f

    def widget_attrs(self, widget):
        attrs = super().widget_attrs(widget)
        if isinstance(widget, forms.widgets.FileInput):
            attrs["accept"] = "image/png,image/jpeg"
        return attrs


class SponsorTierForm(forms.ModelForm):
    logo_width = forms.ChoiceField(
        choices=LOGO_WIDTH_PRESETS + ((CUSTOM_LOGO_WIDTH, _("Custom")),),
        initial="150",
        widget=forms.RadioSelect,
        label=_("Logo width"),
    )
    custom_logo_width = forms.IntegerField(
        required=False,
        min_value=LOGO_WIDTH_MIN,
        max_value=LOGO_WIDTH_MAX,
        label=_("Custom width"),
        help_text=_("Pixels, %(min)s–%(max)s.")
        % {"min": LOGO_WIDTH_MIN, "max": LOGO_WIDTH_MAX},
        widget=forms.NumberInput(attrs={"min": LOGO_WIDTH_MIN, "max": LOGO_WIDTH_MAX}),
    )

    class Meta:
        model = SponsorTier
        fields = ["name", "logo_width"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            width = self.instance.logo_width
            if str(width) in dict(LOGO_WIDTH_PRESETS):
                self.initial["logo_width"] = str(width)
            else:
                # Existing custom width: preselect "Custom" and show the value.
                self.initial["logo_width"] = CUSTOM_LOGO_WIDTH
                self.initial["custom_logo_width"] = width

    def clean(self):
        cleaned_data = super().clean()
        choice = cleaned_data.get("logo_width")
        if choice == CUSTOM_LOGO_WIDTH:
            custom = cleaned_data.get("custom_logo_width")
            if custom is None:
                self.add_error("custom_logo_width", _("Enter a custom width."))
            else:
                cleaned_data["logo_width"] = custom
        elif choice is not None:
            cleaned_data["logo_width"] = int(choice)
        return cleaned_data


class SponsorForm(forms.ModelForm):
    logo = LogoImageField(label=_("Logo"))
    website = forms.URLField(
        required=False,
        assume_scheme="https",
        validators=[validate_https_url],
        label=_("Website"),
    )

    class Meta:
        model = Sponsor
        # "position" stays model-only: order is edited with up/down buttons
        # on the overview page, never through this form.
        fields = ["tier", "name", "logo", "website", "published"]

    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.event = event
        if event is not None:
            self.fields["tier"].queryset = SponsorTier.objects.filter(event=event)
        if self.instance.pk and self.instance.logo:
            # Editing: keep existing logo unless a new one is uploaded.
            self.fields["logo"].required = False

    def clean_tier(self):
        tier = self.cleaned_data.get("tier")
        if (
            tier is not None
            and self.event is not None
            and tier.event_id != self.event.pk
        ):
            raise forms.ValidationError(_("Tier must belong to the same event."))
        return tier
