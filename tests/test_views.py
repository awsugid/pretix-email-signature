from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from pathlib import Path
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


class ThumbnailMarkupTest(ViewTestMixin, TestCase):
    """Contract for CSP-safe logo thumbnails (see memory implementation/thumbnail).

    pretix control CSP ships style-src without 'unsafe-inline', so browsers drop
    inline style attributes; sizing must come from a plugin stylesheet linked
    via the custom_header block.
    """

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def test_index_links_plugin_stylesheet(self):
        self.make_tier()
        response = self.client.get(self.index_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/static/gultix_sponsors/css/control.css"')

    def test_thumbnail_css_ships_size_constraints(self):
        from django.contrib.staticfiles import finders

        path = finders.find("gultix_sponsors/css/control.css")
        self.assertIsNotNone(path)
        css = Path(path).read_text()
        self.assertIn("max-width: 96px", css)
        self.assertIn("max-height: 64px", css)

    def test_logo_img_uses_class_not_inline_style(self):
        tier = self.make_tier()
        self.make_sponsor(tier, "Acme")
        response = self.client.get(self.index_url())
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertEqual(html.count('class="sponsor-thumb"'), 1)
        # regression guard: inline style attr is CSP-blocked, must not come back
        self.assertNotIn('style="height: 32px', html)


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
            {"name": "Gold", "logo_width": "200"},
        )
        self.assertRedirects(response, self.index_url())
        tier.refresh_from_db()
        self.assertEqual(tier.logo_width, 200)

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


class ReorderTest(ViewTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.tiers = [self.make_tier(name=n) for n in ("T1", "T2", "T3")]

    def tier_move_url(self, tier, direction):
        return self.index_url() + "tiers/{}/move/{}".format(tier.pk, direction)

    def sponsor_move_url(self, sponsor, direction):
        return self.index_url() + "sponsors/{}/move/{}".format(sponsor.pk, direction)

    def tier_names(self, event=None):
        return list(
            SponsorTier.objects.filter(event=event or self.event)
            .order_by("position", "pk")
            .values_list("name", flat=True)
        )

    def tier_positions(self):
        return list(
            SponsorTier.objects.filter(event=self.event)
            .order_by("position", "pk")
            .values_list("position", flat=True)
        )

    def sponsor_names(self, tier):
        return list(
            Sponsor.objects.filter(tier=tier)
            .order_by("position", "pk")
            .values_list("name", flat=True)
        )

    def make_tier_sponsors(self, tier, names=("S1", "S2", "S3")):
        return [self.make_sponsor(tier, n) for n in names]

    # --- tiers: moves, boundaries, tie handling -------------------------

    def test_tier_move_up(self):
        # All tiers sit on the default position 0: pk order is the tiebreaker.
        response = self.client.post(self.tier_move_url(self.tiers[2], "up"))
        self.assertRedirects(response, self.index_url())
        self.assertEqual(self.tier_names(), ["T1", "T3", "T2"])
        self.assertEqual(self.tier_positions(), [0, 1, 2])

    def test_tier_move_down(self):
        response = self.client.post(self.tier_move_url(self.tiers[0], "down"))
        self.assertRedirects(response, self.index_url())
        self.assertEqual(self.tier_names(), ["T2", "T1", "T3"])
        self.assertEqual(self.tier_positions(), [0, 1, 2])

    def test_tier_move_up_first_is_noop(self):
        response = self.client.post(self.tier_move_url(self.tiers[0], "up"))
        self.assertRedirects(response, self.index_url())
        self.assertEqual(self.tier_names(), ["T1", "T2", "T3"])

    def test_tier_move_down_last_is_noop(self):
        response = self.client.post(self.tier_move_url(self.tiers[2], "down"))
        self.assertRedirects(response, self.index_url())
        self.assertEqual(self.tier_names(), ["T1", "T2", "T3"])

    def test_tier_move_normalizes_tied_positions(self):
        # Existing rows all default 0 must stay stable by pk until moved.
        self.client.post(self.tier_move_url(self.tiers[1], "up"))
        names = self.tier_names()
        self.assertEqual(names, ["T2", "T1", "T3"])
        self.assertEqual(self.tier_positions(), [0, 1, 2])
        self.assertEqual(len(set(self.tier_positions())), 3)

    # --- sponsors: within-tier moves and boundaries ---------------------

    def test_sponsor_move_up(self):
        sponsors = self.make_tier_sponsors(self.tiers[0])
        response = self.client.post(self.sponsor_move_url(sponsors[2], "up"))
        self.assertRedirects(response, self.index_url())
        self.assertEqual(self.sponsor_names(self.tiers[0]), ["S1", "S3", "S2"])

    def test_sponsor_move_down(self):
        sponsors = self.make_tier_sponsors(self.tiers[0])
        response = self.client.post(self.sponsor_move_url(sponsors[0], "down"))
        self.assertRedirects(response, self.index_url())
        self.assertEqual(self.sponsor_names(self.tiers[0]), ["S2", "S1", "S3"])

    def test_sponsor_move_boundaries_are_noop(self):
        sponsors = self.make_tier_sponsors(self.tiers[0])
        self.client.post(self.sponsor_move_url(sponsors[0], "up"))
        self.assertEqual(self.sponsor_names(self.tiers[0]), ["S1", "S2", "S3"])
        self.client.post(self.sponsor_move_url(sponsors[2], "down"))
        self.assertEqual(self.sponsor_names(self.tiers[0]), ["S1", "S2", "S3"])

    def test_sponsor_move_is_scoped_to_own_tier(self):
        moved_tier, other_tier = self.tiers[0], self.tiers[1]
        sponsors = self.make_tier_sponsors(moved_tier)
        self.make_tier_sponsors(other_tier)
        self.client.post(self.sponsor_move_url(sponsors[0], "down"))
        self.assertEqual(self.sponsor_names(moved_tier), ["S2", "S1", "S3"])
        self.assertEqual(self.sponsor_names(other_tier), ["S1", "S2", "S3"])
        # Sibling tier's sponsors keep their untouched default positions.
        self.assertEqual(
            list(
                Sponsor.objects.filter(tier=other_tier)
                .order_by("pk")
                .values_list("position", flat=True)
            ),
            [0, 0, 0],
        )

    # --- new items append at the end ------------------------------------

    def test_new_tier_appended_last(self):
        for name in ("N1", "N2"):
            response = self.client.post(
                self.index_url() + "tiers/add",
                {"name": name, "logo_width": "150"},
            )
            self.assertRedirects(response, self.index_url())
        self.assertEqual(self.tier_names(), ["T1", "T2", "T3", "N1", "N2"])
        self.assertEqual(self.tier_positions(), [0, 0, 0, 1, 2])

    def test_new_sponsor_appended_last(self):
        tier = self.tiers[0]
        self.make_sponsor(tier, "First")
        for name in ("Second", "Third"):
            response = self.client.post(
                self.index_url() + "sponsors/add",
                {
                    "tier": tier.pk,
                    "name": name,
                    "website": "",
                    "published": "on",
                    "logo": SimpleUploadedFile("a.png", PNG, content_type="image/png"),
                },
            )
            self.assertRedirects(response, self.index_url())
        self.assertEqual(self.sponsor_names(tier), ["First", "Second", "Third"])

    # --- access control --------------------------------------------------

    def test_tier_move_other_event_not_found(self):
        other = Event.objects.create(
            organizer=self.organizer,
            name="Other",
            slug="other",
            date_from=timezone.now(),
        )
        foreign = self.make_tier(event=other, name="Foreign")
        response = self.client.post(self.tier_move_url(foreign, "up"))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            list(
                SponsorTier.objects.filter(event=other)
                .order_by("pk")
                .values_list("position", flat=True)
            ),
            [0],
        )

    def test_sponsor_move_other_event_not_found(self):
        other = Event.objects.create(
            organizer=self.organizer,
            name="Other2",
            slug="other2",
            date_from=timezone.now(),
        )
        foreign_tier = self.make_tier(event=other, name="Foreign")
        foreign_sponsor = self.make_sponsor(foreign_tier, "Evil")
        response = self.client.post(self.sponsor_move_url(foreign_sponsor, "up"))
        self.assertEqual(response.status_code, 404)
        foreign_sponsor.refresh_from_db()
        self.assertEqual(foreign_sponsor.position, 0)

    def test_move_get_not_allowed(self):
        sponsors = self.make_tier_sponsors(self.tiers[0])
        response = self.client.get(self.tier_move_url(self.tiers[0], "up"))
        self.assertEqual(response.status_code, 405)
        response = self.client.get(self.sponsor_move_url(sponsors[0], "down"))
        self.assertEqual(response.status_code, 405)
        self.assertEqual(self.tier_names(), ["T1", "T2", "T3"])

    def test_move_requires_authentication(self):
        self.client.logout()
        response = self.client.post(self.tier_move_url(self.tiers[0], "up"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/control/login", response["Location"])

    def test_move_hidden_without_team(self):
        sponsor = self.make_sponsor(self.tiers[0], "S")
        self.client.force_login(self.outsider)
        response = self.client.post(self.tier_move_url(self.tiers[0], "up"))
        self.assertEqual(response.status_code, 404)
        response = self.client.post(self.sponsor_move_url(sponsor, "up"))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.tier_names(), ["T1", "T2", "T3"])

    def test_move_requires_csrf_token(self):
        from django.test import Client

        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        response = csrf_client.post(self.tier_move_url(self.tiers[1], "up"))
        self.assertEqual(response.status_code, 403)
        sponsor = self.make_sponsor(self.tiers[0], "S")
        response = csrf_client.post(self.sponsor_move_url(sponsor, "up"))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.tier_names(), ["T1", "T2", "T3"])

    # --- UI contract: buttons, labels, no numeric inputs ------------------

    def test_index_renders_disabled_boundary_buttons(self):
        self.make_tier_sponsors(self.tiers[0], ("S1", "S2"))
        self.make_tier_sponsors(self.tiers[1], ("S3", "S4"))
        response = self.client.get(self.index_url())
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        # 2 tier boundary buttons (first up, last down)
        # + 2 boundary buttons per sponsored tier (2 tiers) = 6 disabled.
        # (" disabled>" avoids false hits from unrelated strings in the base
        # template's bundled JavaScript.)
        self.assertEqual(html.count(" disabled>"), 6)

    def test_move_buttons_have_accessible_labels(self):
        self.make_sponsor(self.tiers[0], "Acme")
        response = self.client.get(self.index_url())
        self.assertContains(response, 'aria-label="Move tier T1 up"')
        self.assertContains(response, 'aria-label="Move sponsor Acme up"')
        self.assertContains(response, "fa-arrow-up")
        self.assertContains(response, "fa-arrow-down")

    def test_forms_no_longer_render_position_input(self):
        sponsor = self.make_sponsor(self.tiers[0], "Acme")
        urls = [
            self.index_url() + "tiers/add",
            self.index_url() + "tiers/{}/edit".format(self.tiers[0].pk),
            self.index_url() + "sponsors/add",
            self.index_url() + "sponsors/{}/edit".format(sponsor.pk),
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertNotContains(response, 'name="position"')
