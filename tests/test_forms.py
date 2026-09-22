import unittest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from pretix.base.models import Event, Organizer

from gultix_sponsors.models import SponsorTier

try:
    from gultix_sponsors.forms import SponsorForm, SponsorTierForm

    HAVE_FORMS = True
except ImportError:  # pragma: no cover - forms agent deliverable
    HAVE_FORMS = False

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c6300010000050001"
    "0d0a2db40000000049454e44ae426082"
)


def make_event(slug="t"):
    organizer = Organizer.objects.create(name="O", slug="o" + slug)
    return Event.objects.create(
        organizer=organizer, name="Event", slug=slug, date_from=timezone.now()
    )


def sponsor_payload(tier, **overrides):
    payload = {
        "tier": tier.pk,
        "name": "Acme",
        "website": "",
        "position": 0,
        "published": "on",
    }
    payload.update(overrides)
    return payload


@unittest.skipUnless(HAVE_FORMS, "gultix_sponsors.forms not available")
class SponsorTierFormTest(TestCase):
    def test_valid_preset(self):
        make_event()
        form = SponsorTierForm(
            data={"name": "Gold", "position": 1, "logo_width": "100"}
        )
        self.assertTrue(form.is_valid(), form.errors)
        tier = form.save(commit=False)
        self.assertEqual(tier.logo_width, 100)

    def test_valid_custom_width(self):
        make_event()
        form = SponsorTierForm(
            data={
                "name": "Gold",
                "position": 0,
                "logo_width": "custom",
                "custom_logo_width": 120,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        tier = form.save(commit=False)
        self.assertEqual(tier.logo_width, 120)

    def test_custom_choice_requires_value(self):
        make_event()
        form = SponsorTierForm(
            data={"name": "Gold", "position": 0, "logo_width": "custom"}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("custom_logo_width", form.errors)

    def test_custom_width_bounds(self):
        make_event()
        for width in (39, 301):
            form = SponsorTierForm(
                data={
                    "name": "Gold",
                    "position": 0,
                    "logo_width": "custom",
                    "custom_logo_width": width,
                }
            )
            self.assertFalse(form.is_valid())
            self.assertIn("custom_logo_width", form.errors)

    def test_default_choice_is_medium_preset(self):
        form = SponsorTierForm()
        self.assertEqual(form.fields["logo_width"].initial, "150")


@unittest.skipUnless(HAVE_FORMS, "gultix_sponsors.forms not available")
class SponsorFormTest(TestCase):
    def logo(self):
        return {"logo": SimpleUploadedFile("a.png", PNG, content_type="image/png")}

    def test_valid(self):
        event = make_event()
        tier = SponsorTier.objects.create(event=event, name="Gold")
        form = SponsorForm(data=sponsor_payload(tier), files=self.logo(), event=event)
        self.assertTrue(form.is_valid(), form.errors)

    def test_malformed_upload_rejected(self):
        event = make_event()
        tier = SponsorTier.objects.create(event=event, name="Gold")
        form = SponsorForm(
            data=sponsor_payload(tier),
            files={
                "logo": SimpleUploadedFile(
                    "a.png", b"not an image", content_type="image/png"
                )
            },
            event=event,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("logo", form.errors)

    def test_http_website_rejected(self):
        event = make_event()
        tier = SponsorTier.objects.create(event=event, name="Gold")
        form = SponsorForm(
            data=sponsor_payload(tier, website="http://example.com"),
            files=self.logo(),
            event=event,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("website", form.errors)

    def test_foreign_event_tier_rejected(self):
        event = make_event("a")
        other = make_event("b")
        foreign_tier = SponsorTier.objects.create(event=other, name="Foreign")
        form = SponsorForm(
            data=sponsor_payload(foreign_tier), files=self.logo(), event=event
        )
        self.assertFalse(form.is_valid())
        self.assertIn("tier", form.errors)
