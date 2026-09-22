from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from html.parser import HTMLParser
from pretix.base.models import Event, Organizer

from gultix_sponsors.email import GultixSponsorsMailRenderer
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

    def render(self, event, body="Hello body", signature="Best regards"):
        return GultixSponsorsMailRenderer(event).render(
            body, signature, "Subject", None, None, None
        )


class RendererRegistrationTest(RendererTestMixin, TestCase):
    def test_renderer_registered_when_plugin_enabled(self):
        event = self.make_event()
        event.plugins = "gultix_sponsors"
        event.save()
        renderers = event.get_html_mail_renderers()
        self.assertIn("gultix_sponsors", renderers)
        self.assertIsInstance(renderers["gultix_sponsors"], GultixSponsorsMailRenderer)

    def test_renderer_not_registered_when_plugin_disabled(self):
        event = self.make_event()
        renderers = event.get_html_mail_renderers()
        self.assertNotIn("gultix_sponsors", renderers)
        # core renderers stay untouched
        self.assertIn("classic", renderers)


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
