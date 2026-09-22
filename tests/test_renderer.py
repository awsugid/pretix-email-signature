from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from html.parser import HTMLParser
from pretix.base.models import Event, Organizer

from gultix_sponsors.email import (
    GultixSponsorsMailRenderer,
    GultixSponsorsSimpleLogoMailRenderer,
)
from gultix_sponsors.models import Sponsor, SponsorTier
from gultix_sponsors.signals import nav_event_link

# Minimal valid 1x1 PNG.
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c6300010000050001"
    "0d0a2db40000000049454e44ae426082"
)


class RendererTestMixin:
    def make_event(self, slug="t"):
        organizer = Organizer.objects.create(name="O", slug="o" + slug)
        return Event.objects.create(
            organizer=organizer,
            name="Event " + slug,
            slug=slug,
            date_from=timezone.now(),
        )

    def make_sponsor(self, tier, name, published=True, website="", position=0):
        return Sponsor.objects.create(
            tier=tier,
            name=name,
            published=published,
            website=website,
            position=position,
            logo=SimpleUploadedFile("logo.png", PNG, content_type="image/png"),
        )

    renderer_class = GultixSponsorsMailRenderer

    def render(self, event, body="Hello body", signature="Best regards"):
        return self.renderer_class(event).render(
            body, signature, "Subject", None, None, None
        )


class RendererRegistrationTest(RendererTestMixin, TestCase):
    def test_renderers_registered_when_plugin_enabled(self):
        event = self.make_event()
        event.plugins = "gultix_sponsors"
        event.save()
        renderers = event.get_html_mail_renderers()
        self.assertIn("gultix_sponsors", renderers)
        self.assertIn("gultix_sponsors_simple_logo", renderers)
        self.assertIsInstance(renderers["gultix_sponsors"], GultixSponsorsMailRenderer)
        self.assertIsInstance(
            renderers["gultix_sponsors_simple_logo"],
            GultixSponsorsSimpleLogoMailRenderer,
        )

    def test_renderers_not_registered_when_plugin_disabled(self):
        event = self.make_event()
        renderers = event.get_html_mail_renderers()
        self.assertNotIn("gultix_sponsors", renderers)
        self.assertNotIn("gultix_sponsors_simple_logo", renderers)
        # core renderers stay untouched
        self.assertIn("classic", renderers)
        self.assertIn("simple_logo", renderers)

    def test_renderer_identifiers_and_config_stable(self):
        # original renderer must keep its identity; the new one is distinct
        self.assertEqual(GultixSponsorsMailRenderer.identifier, "gultix_sponsors")
        self.assertEqual(
            GultixSponsorsMailRenderer.template_name,
            "gultix_sponsors/email/sponsors_wrapper.html",
        )
        self.assertEqual(
            GultixSponsorsSimpleLogoMailRenderer.identifier,
            "gultix_sponsors_simple_logo",
        )
        self.assertEqual(
            GultixSponsorsSimpleLogoMailRenderer.template_name,
            "gultix_sponsors/email/simple_logo_sponsors.html",
        )
        self.assertEqual(
            GultixSponsorsSimpleLogoMailRenderer.thumbnail_filename,
            "pretixbase/email/thumb_simple_logo.png",
        )


class RendererRenderingTest(RendererTestMixin, TestCase):
    def test_no_sponsors_no_footer(self):
        event = self.make_event()
        html = self.render(event)
        self.assertNotIn("gultix-sponsors", html)

    def test_footer_below_signature(self):
        event = self.make_event()
        tier = SponsorTier.objects.create(event=event, name="Gold")
        self.make_sponsor(tier, "Acme")
        html = self.render(event)
        self.assertIn("gultix-sponsors", html)
        self.assertIn("Best regards", html)
        self.assertGreater(html.index("gultix-sponsors"), html.index("Best regards"))

    def test_footer_below_body_when_signature_empty(self):
        event = self.make_event()
        tier = SponsorTier.objects.create(event=event, name="Gold")
        self.make_sponsor(tier, "Acme")
        html = self.render(event, signature="")
        self.assertIn("gultix-sponsors", html)
        self.assertGreater(html.index("gultix-sponsors"), html.index("Hello body"))

    def test_sponsored_by_heading_shown_once_before_tiers(self):
        event = self.make_event()
        gold = SponsorTier.objects.create(event=event, name="Gold")
        silver = SponsorTier.objects.create(event=event, name="Silver", position=2)
        self.make_sponsor(gold, "Acme")
        self.make_sponsor(silver, "Linked")
        html = self.render(event)
        self.assertEqual(html.count("Sponsored by"), 1)
        self.assertLess(html.index("Sponsored by"), html.index("Gold"))
        self.assertLess(html.index("Sponsored by"), html.index("Silver"))

    def test_sponsored_by_heading_absent_when_empty(self):
        event = self.make_event()
        html = self.render(event)
        self.assertNotIn("Sponsored by", html)

    def test_unpublished_sponsors_hidden(self):
        event = self.make_event()
        tier = SponsorTier.objects.create(event=event, name="Gold")
        self.make_sponsor(tier, "Hidden", published=False)
        html = self.render(event)
        self.assertNotIn("gultix-sponsors", html)
        self.assertNotIn("Hidden", html)

    def test_published_sponsor_without_logo_skipped(self):
        event = self.make_event()
        tier = SponsorTier.objects.create(event=event, name="Gold")
        Sponsor.objects.create(tier=tier, name="Logoless", published=True)
        html = self.render(event)
        self.assertNotIn("gultix-sponsors", html)
        self.assertNotIn("Logoless", html)

    def test_visible_sponsor_name_and_tier_heading(self):
        event = self.make_event()
        tier = SponsorTier.objects.create(event=event, name="Gold")
        self.make_sponsor(tier, "Acme")
        html = self.render(event)
        # tier heading and sponsor name are visible text, not just alt text
        self.assertIn(">Gold</div>", html)
        self.assertIn(">Acme</div>", html)

    def test_tier_with_only_unpublished_sponsors_omitted(self):
        event = self.make_event()
        hidden_tier = SponsorTier.objects.create(event=event, name="Hidden tier")
        self.make_sponsor(hidden_tier, "Hidden", published=False)
        visible_tier = SponsorTier.objects.create(event=event, name="Visible")
        self.make_sponsor(visible_tier, "Acme")
        html = self.render(event)
        self.assertIn("Acme", html)
        self.assertNotIn("Hidden", html)

    def test_event_isolation(self):
        event_a = self.make_event("a")
        tier = SponsorTier.objects.create(event=event_a, name="Gold")
        self.make_sponsor(tier, "Acme")
        event_b = self.make_event("b")
        self.assertIn("Acme", self.render(event_a))
        self.assertNotIn("gultix-sponsors", self.render(event_b))

    def test_configured_width_used(self):
        event = self.make_event()
        tier = SponsorTier.objects.create(event=event, name="Gold", logo_width=200)
        self.make_sponsor(tier, "Acme")
        html = self.render(event)
        self.assertIn('width="200"', html)
        self.assertIn("width: 200px", html)
        self.assertIn("max-width: 100%", html)

    def test_website_link_and_img_without_website(self):
        event = self.make_event()
        tier = SponsorTier.objects.create(event=event, name="Gold")
        self.make_sponsor(tier, "Linked", website="https://example.com/sponsor")
        self.make_sponsor(tier, "Plain")
        html = self.render(event)
        footer = html.split("gultix-sponsors", 1)[1]
        self.assertIn('href="https://example.com/sponsor"', footer)
        self.assertEqual(footer.count("<a href="), 1)

    def test_public_uuid_logo_urls(self):
        event = self.make_event()
        tier = SponsorTier.objects.create(event=event, name="Gold")
        sponsor = self.make_sponsor(tier, "Acme")
        html = self.render(event)
        self.assertIn(sponsor.logo.url, html)
        self.assertRegex(sponsor.logo.name, r"^pub/gultix-sponsors/[0-9a-f]{32}\.png$")

    def test_relative_media_url_prefixed_with_site_url(self):
        event = self.make_event()
        tier = SponsorTier.objects.create(event=event, name="Gold")
        sponsor = self.make_sponsor(tier, "Acme")
        html = self.render(event)
        # pretix pattern (simple_logo.html): prefix site_url when URL is
        # root-relative; emails must not rely on the mail client's base URL.
        self.assertIn('src="http://example.com{}'.format(sponsor.logo.url), html)
        self.assertNotIn('src="{}'.format(sponsor.logo.url), html)

    def test_names_escaped(self):
        event = self.make_event()
        tier = SponsorTier.objects.create(event=event, name="Gold")
        self.make_sponsor(tier, '<script>alert("X&Y")</script>')
        html = self.render(event)
        # Quotes and ampersands are escaped, so the name cannot break out of
        # the alt attribute; it must never become a script *element*.
        self.assertIn("alert(&quot;X&amp;Y&quot;)", html)

        class ElementCollector(HTMLParser):
            tags = []

            def handle_starttag(self, tag, attrs):
                self.tags.append(tag)

        collector = ElementCollector()
        collector.feed(html)
        self.assertNotIn("script", collector.tags)

    def test_tier_and_sponsor_ordering(self):
        event = self.make_event()
        gold = SponsorTier.objects.create(event=event, name="Gold", position=2)
        silver = SponsorTier.objects.create(event=event, name="Silver", position=1)
        self.make_sponsor(gold, "GoldFirst", position=1)
        self.make_sponsor(gold, "GoldSecond", position=2)
        self.make_sponsor(silver, "SilverFirst")
        html = self.render(event)
        footer = html.split("gultix-sponsors", 1)[1]
        self.assertLess(footer.index("SilverFirst"), footer.index("GoldFirst"))
        self.assertLess(footer.index("GoldFirst"), footer.index("GoldSecond"))


class RendererStressMatrixTest(RendererTestMixin, TestCase):
    """Stress matrix from the local browser run: every supported width,
    mixed aspect ratios and unbreakable long names."""

    def test_all_supported_widths_render_exactly(self):
        event = self.make_event()
        for i, width in enumerate((40, 100, 150, 200, 300)):
            tier = SponsorTier.objects.create(
                event=event, name="W%d" % width, logo_width=width, position=i
            )
            self.make_sponsor(tier, "S%d" % width)
        html = self.render(event)
        for width in (40, 100, 150, 200, 300):
            self.assertIn('width="%d"' % width, html)
            self.assertIn("width: %dpx" % width, html)
            self.assertIn("max-width: %dpx" % width, html)
        # aspect ratio is preserved via height: auto
        self.assertIn("height: auto", html)

    def test_aspect_ratio_preserved_via_height_auto(self):
        event = self.make_event()
        tier = SponsorTier.objects.create(event=event, name="Gold", logo_width=300)
        self.make_sponsor(tier, "Wide")
        html = self.render(event)
        img = next(c for c in html.split("<img") if 'alt="Wide"' in c)
        self.assertIn('width="300"', img)
        self.assertIn("height: auto", img)
        # no fixed height attribute may fight the auto style
        self.assertNotIn('height="', img)

    def test_long_unbreakable_names_wrap(self):
        event = self.make_event()
        tier = SponsorTier.objects.create(event=event, name="T" * 100, logo_width=100)
        self.make_sponsor(tier, "X" * 190)
        html = self.render(event)
        footer = html.split("gultix-sponsors", 1)[1]
        # tier heading and sponsor name must both break instead of
        # overflowing the email container (word-wrap works in Outlook 2007+)
        self.assertEqual(footer.count("word-wrap: break-word"), 2)
        self.assertIn("overflow-wrap: break-word", footer)
        self.assertIn("X" * 190, footer)


class SimpleLogoRendererRenderingTest(RendererRenderingTest):
    """The full classic-layout suite, rerun against the simple-with-logo
    layout, so both designs keep identical sponsor-footer semantics."""

    renderer_class = GultixSponsorsSimpleLogoMailRenderer


class SimpleLogoRendererStressMatrixTest(RendererStressMatrixTest):
    renderer_class = GultixSponsorsSimpleLogoMailRenderer


class SimpleLogoRendererTest(RendererTestMixin, TestCase):
    """Behavior specific to the simple-with-logo variant."""

    renderer_class = GultixSponsorsSimpleLogoMailRenderer

    def test_event_logo_retained_with_sponsors(self):
        from django.core.files.base import ContentFile
        from django.core.files.storage import default_storage

        event = self.make_event()
        stored = default_storage.save(
            "pub/gultix-sponsors-tests/event-logo.png", ContentFile(PNG)
        )
        event.settings.logo_image = default_storage.open(stored)
        tier = SponsorTier.objects.create(event=event, name="Gold")
        self.make_sponsor(tier, "Acme")
        html = self.render(event)
        # the layout's own logo header row survives next to the sponsor footer
        self.assertIn('alt="Event t"', html)
        self.assertIn("gultix-sponsors", html)
        self.assertLess(html.index('alt="Event t"'), html.index("gultix-sponsors"))

    def test_no_event_logo_no_logo_row(self):
        event = self.make_event()
        html = self.render(event)
        self.assertNotIn('alt="Event t"', html)
        # the header still names the event as a plain link
        self.assertIn("Event t", html)


class NavSignalTest(TestCase):
    def _request(self, granted, resolver_match=None):
        from types import SimpleNamespace

        return SimpleNamespace(
            user=SimpleNamespace(
                has_event_permission=lambda *a, **k: granted,
            ),
            resolver_match=resolver_match,
        )

    def test_nav_denied_without_permission(self):
        organizer = Organizer.objects.create(name="O", slug="o")
        event = Event.objects.create(
            organizer=organizer, name="E", slug="e", date_from=timezone.now()
        )
        request = self._request(granted=False)
        request.event = event
        request.organizer = organizer
        self.assertEqual(nav_event_link(event, request), [])

    def test_nav_url_resolves_to_ui_index(self):
        from django.urls import set_urlconf

        organizer = Organizer.objects.create(name="O", slug="o")
        event = Event.objects.create(
            organizer=organizer, name="E", slug="e", date_from=timezone.now()
        )
        request = self._request(granted=True)
        request.event = event
        request.organizer = organizer
        try:
            set_urlconf("pretix.multidomain.maindomain_urlconf")
            response = nav_event_link(event, request)
        finally:
            set_urlconf(None)
        self.assertEqual(len(response), 1)
        self.assertEqual(
            response[0]["url"],
            "/control/event/o/e/gultix_sponsors/",
        )
        self.assertEqual(response[0]["label"], "Sponsors")
