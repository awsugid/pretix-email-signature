from django.dispatch import receiver
from django.urls import NoReverseMatch, reverse
from django.utils.translation import gettext_lazy
from pretix.base.signals import register_html_mail_renderers
from pretix.control.signals import nav_event


@receiver(register_html_mail_renderers, dispatch_uid="gultix_sponsors_mail_renderers")
def register_mail_renderers(sender, **kwargs):
    from .email import (
        GultixSponsorsMailRenderer,
        GultixSponsorsSimpleLogoMailRenderer,
    )

    return [GultixSponsorsMailRenderer, GultixSponsorsSimpleLogoMailRenderer]


@receiver(nav_event, dispatch_uid="gultix_sponsors_nav_event")
def nav_event_link(sender, request, **kwargs):
    if not request.user.has_event_permission(
        request.organizer,
        request.event,
        "event.settings.general:write",
        request=request,
    ):
        return []
    try:
        url = reverse(
            "plugins:gultix_sponsors:index",
            kwargs={
                "event": request.event.slug,
                "organizer": request.organizer.slug,
            },
        )
    except NoReverseMatch:
        # UI urls not installed (yet); do not break event navigation.
        return []
    return [
        {
            "label": gettext_lazy("Sponsors"),
            "url": url,
            "active": (
                request.resolver_match.namespace == "plugins:gultix_sponsors"
                if request.resolver_match
                else False
            ),
            "icon": "ticket",
        }
    ]
