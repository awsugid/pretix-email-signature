from django.utils.translation import gettext_lazy
from pretix.base.email import ClassicMailRenderer


class GultixSponsorsMailRenderer(ClassicMailRenderer):
    """Classic renderer plus a sponsor footer below the signature (or body).

    Plain-text emails are built outside of the renderer and stay untouched.
    """

    verbose_name = gettext_lazy("Default with sponsors")
    identifier = "gultix_sponsors"
    thumbnail_filename = "pretixbase/email/thumb.png"  # reuse host thumbnail
    template_name = "gultix_sponsors/email/sponsors_wrapper.html"

    def render(
        self,
        plain_body,
        plain_signature,
        subject,
        order=None,
        position=None,
        context=None,
    ):
        # ponytail: TemplateBasedMailRenderer.render has no context hook, so
        # sponsor rows travel through a transient attribute on the event
        # instance; switch to a real hook if pretix ever adds one.
        if self.event is not None:
            self.event.gultix_sponsor_footer_tiers = self._footer_tiers()
        return super().render(
            plain_body, plain_signature, subject, order, position, context
        )

    def _footer_tiers(self):
        tiers = []
        for tier in self.event.sponsor_tiers.prefetch_related("sponsors"):
            # Defensive: never render a published sponsor without an uploaded logo.
            sponsors = [s for s in tier.sponsors.all() if s.published and s.logo]
            if sponsors:
                tiers.append((tier, sponsors))
        return tiers
