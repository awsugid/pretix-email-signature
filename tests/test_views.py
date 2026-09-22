from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from pretix.base.models import Event, Organizer, Team, User

from gultix_sponsors.models import Sponsor, SponsorTier

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c6300010000050001"
    "0d0a2db40000000049454e44ae426082"
)


class ViewTestMixin:
    def setUp(self):
        self.organizer = Organizer.objects.create(name="O", slug="o")
        self.event = Event.objects.create(
            organizer=self.organizer,
            name="Event",
            slug="e",
            date_from=timezone.now(),
        )
        self.user = User.objects.create_user("admin@test", "testpwd", fullname="John")
        self.team = Team.objects.create(
            organizer=self.organizer,
            name="Sponsors team",
            all_events=True,
            all_event_permissions=True,
        )
        self.team.members.add(self.user)
        self.outsider = User.objects.create_user("out@test", "testpwd", fullname="Out")

    def index_url(self, event=None):
        return "/control/event/{}/{}/gultix_sponsors/".format(
            event.organizer.slug if event else self.organizer.slug,
            event.slug if event else self.event.slug,
        )

    def make_tier(self, event=None, **kwargs):
        return SponsorTier.objects.create(
            event=event or self.event, name=kwargs.pop("name", "Gold"), **kwargs
        )

    def make_sponsor(self, tier, name="Acme", **kwargs):
        kwargs.setdefault("published", True)
        return Sponsor.objects.create(
            tier=tier,
            name=name,
            logo=SimpleUploadedFile("logo.png", PNG, content_type="image/png"),
            **kwargs,
        )


class PermissionTest(ViewTestMixin, TestCase):
    def test_index_requires_authentication(self):
        response = self.client.get(self.index_url())
        self.assertEqual(response.status_code, 302)
        self.assertIn("/control/login", response["Location"])

    def test_index_hidden_without_team(self):
        # pretix serves 404, not 403, for events the user has no access to
        self.client.force_login(self.outsider)
        response = self.client.get(self.index_url())
        self.assertEqual(response.status_code, 404)

    def test_index_allowed_with_permission(self):
        self.client.force_login(self.user)
        response = self.client.get(self.index_url())
        self.assertEqual(response.status_code, 200)

    def test_tier_delete_hidden_without_team(self):
        tier = self.make_tier()
        self.client.force_login(self.outsider)
        response = self.client.post(
            self.index_url() + "tiers/{}/delete".format(tier.pk)
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(SponsorTier.objects.filter(pk=tier.pk).exists())


class IsolationTest(ViewTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.other = Event.objects.create(
            organizer=self.organizer,
            name="Other",
            slug="other",
            date_from=timezone.now(),
        )
        self.client.force_login(self.user)

    def test_tier_of_other_event_not_found(self):
        tier = self.make_tier(event=self.other)
        response = self.client.get(self.index_url() + "tiers/{}/edit".format(tier.pk))
        self.assertEqual(response.status_code, 404)

    def test_sponsor_of_other_event_not_found(self):
        tier = self.make_tier(event=self.other)
        sponsor = self.make_sponsor(tier)
        response = self.client.get(
            self.index_url() + "sponsors/{}/edit".format(sponsor.pk)
        )
        self.assertEqual(response.status_code, 404)

    def test_foreign_tier_rejected_on_sponsor_create(self):
        self.make_tier()  # own tier so dispatch() does not redirect
        tier = self.make_tier(event=self.other)
        response = self.client.post(
            self.index_url() + "sponsors/add",
            {
                "tier": tier.pk,
                "name": "Evil",
                "website": "",
                "position": 0,
                "published": "on",
            },
        )
        self.assertEqual(response.status_code, 200)  # form error, no redirect
        self.assertFalse(Sponsor.objects.filter(name="Evil").exists())


class CrudTest(ViewTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def test_tier_create_with_preset(self):
        response = self.client.post(
            self.index_url() + "tiers/add",
            {"name": "Silver", "position": 1, "logo_width": "100"},
        )
        self.assertRedirects(response, self.index_url())
        tier = SponsorTier.objects.get(name="Silver")
        self.assertEqual(tier.logo_width, 100)
        self.assertEqual(tier.event, self.event)

    def test_tier_create_with_custom_width(self):
        response = self.client.post(
            self.index_url() + "tiers/add",
            {
                "name": "Silver",
                "position": 1,
                "logo_width": "custom",
                "custom_logo_width": 120,
            },
        )
        self.assertRedirects(response, self.index_url())
        self.assertEqual(SponsorTier.objects.get(name="Silver").logo_width, 120)

    def test_tier_update(self):
        tier = self.make_tier(name="Gold")
        response = self.client.post(
            self.index_url() + "tiers/{}/edit".format(tier.pk),
            {"name": "Gold", "position": 2, "logo_width": "200"},
        )
        self.assertRedirects(response, self.index_url())
        tier.refresh_from_db()
        self.assertEqual(tier.logo_width, 200)
        self.assertEqual(tier.position, 2)

    def test_tier_delete_get_shows_confirmation_no_delete(self):
        tier = self.make_tier()
        response = self.client.get(self.index_url() + "tiers/{}/delete".format(tier.pk))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(SponsorTier.objects.filter(pk=tier.pk).exists())

    def test_tier_delete_post_deletes(self):
        tier = self.make_tier()
        response = self.client.post(
            self.index_url() + "tiers/{}/delete".format(tier.pk)
        )
        self.assertRedirects(response, self.index_url())
        self.assertFalse(SponsorTier.objects.filter(pk=tier.pk).exists())

    def test_sponsor_create(self):
        tier = self.make_tier()
        response = self.client.post(
            self.index_url() + "sponsors/add",
            {
                "tier": tier.pk,
                "name": "Acme",
                "website": "https://example.com",
                "position": 0,
                "published": "on",
                "logo": SimpleUploadedFile("a.png", PNG, content_type="image/png"),
            },
        )
        self.assertRedirects(response, self.index_url())
        sponsor = Sponsor.objects.get(name="Acme")
        self.assertEqual(sponsor.tier, tier)
        self.assertTrue(sponsor.published)

    def test_sponsor_update_keeps_logo_without_reupload(self):
        tier = self.make_tier()
        sponsor = self.make_sponsor(tier, "Acme", published=False)
        old_name = sponsor.logo.name
        response = self.client.post(
            self.index_url() + "sponsors/{}/edit".format(sponsor.pk),
            {
                "tier": tier.pk,
                "name": "Acme",
                "website": "",
                "position": 0,
                "published": "on",
            },
        )
        self.assertRedirects(response, self.index_url())
        sponsor.refresh_from_db()
        self.assertTrue(sponsor.published)
        self.assertEqual(sponsor.logo.name, old_name)

    def test_sponsor_delete_get_shows_confirmation_no_delete(self):
        tier = self.make_tier()
        sponsor = self.make_sponsor(tier)
        response = self.client.get(
            self.index_url() + "sponsors/{}/delete".format(sponsor.pk)
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Sponsor.objects.filter(pk=sponsor.pk).exists())

    def test_sponsor_delete_post_deletes(self):
        tier = self.make_tier()
        sponsor = self.make_sponsor(tier)
        response = self.client.post(
            self.index_url() + "sponsors/{}/delete".format(sponsor.pk)
        )
        self.assertRedirects(response, self.index_url())
        self.assertFalse(Sponsor.objects.filter(pk=sponsor.pk).exists())
