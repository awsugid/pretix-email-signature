from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from pretix.base.models import Event, Organizer

from gultix_sponsors.models import Sponsor, SponsorTier, validate_https_url

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c6300010000050001"
    "0d0a2db40000000049454e44ae426082"
)


class ModelTestMixin:
    def make_event(self, slug="t"):
        organizer = Organizer.objects.create(name="O", slug="o" + slug)
        return Event.objects.create(
            organizer=organizer, name="Event", slug=slug, date_from=timezone.now()
        )


class SponsorTierModelTest(ModelTestMixin, TestCase):
    def test_ordering_position_pk(self):
        event = self.make_event()
        first = SponsorTier.objects.create(event=event, name="A", position=1)
        zero = SponsorTier.objects.create(event=event, name="B", position=0)
        same = SponsorTier.objects.create(event=event, name="C", position=1)
        self.assertEqual(
            list(SponsorTier.objects.filter(event=event)), [zero, first, same]
        )

    def test_defaults(self):
        tier = SponsorTier(event=self.make_event(), name="A")
        self.assertEqual(tier.logo_width, 150)
        tier.full_clean()  # default within 40..300

    def test_logo_width_bounds(self):
        event = self.make_event()
        for width in (39, 301):
            tier = SponsorTier(event=event, name="A", logo_width=width)
            with self.assertRaises(ValidationError):
                tier.full_clean()


class SponsorModelTest(ModelTestMixin, TestCase):
    def make_tier(self, event):
        return SponsorTier.objects.create(event=event, name="Gold")

    def test_defaults(self):
        sponsor = Sponsor(tier=self.make_tier(self.make_event()), name="A")
        self.assertFalse(sponsor.published)
        self.assertEqual(sponsor.position, 0)

    def test_ordering_position_pk(self):
        event = self.make_event()
        tier = self.make_tier(event)
        b = Sponsor.objects.create(tier=tier, name="B", position=1)
        a = Sponsor.objects.create(tier=tier, name="A", position=0)
        c = Sponsor.objects.create(tier=tier, name="C", position=1)
        self.assertEqual(list(tier.sponsors.all()), [a, b, c])

    def test_logo_unguessable_public_path(self):
        event = self.make_event()
        sponsor = Sponsor.objects.create(
            tier=self.make_tier(event),
            name="A",
            logo=SimpleUploadedFile("logo.png", PNG, content_type="image/png"),
        )
        self.assertRegex(sponsor.logo.name, r"^pub/gultix-sponsors/[0-9a-f]{32}\.png$")

    def test_replacement_preserves_old_file(self):
        event = self.make_event()
        sponsor = Sponsor.objects.create(
            tier=self.make_tier(event),
            name="A",
            logo=SimpleUploadedFile("logo.png", PNG, content_type="image/png"),
        )
        old_name = sponsor.logo.name
        sponsor.logo = SimpleUploadedFile("new.png", PNG, content_type="image/png")
        sponsor.save()
        self.assertNotEqual(sponsor.logo.name, old_name)
        self.assertTrue(default_storage.exists(old_name))

    def test_website_https_only(self):
        with self.assertRaises(ValidationError):
            validate_https_url("http://example.com")
        validate_https_url("https://example.com")  # no error
