from django.urls import re_path

from . import views

urlpatterns = [
    re_path(
        r"^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/gultix_sponsors/$",
        views.SponsorIndexView.as_view(),
        name="index",
    ),
    re_path(
        r"^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/gultix_sponsors/tiers/add$",
        views.TierCreate.as_view(),
        name="tier.add",
    ),
    re_path(
        r"^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/gultix_sponsors/tiers/(?P<tier>\d+)/edit$",
        views.TierUpdate.as_view(),
        name="tier.edit",
    ),
    re_path(
        r"^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/gultix_sponsors/tiers/(?P<tier>\d+)/move/(?P<direction>up|down)$",
        views.TierMove.as_view(),
        name="tier.move",
    ),
    re_path(
        r"^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/gultix_sponsors/tiers/(?P<tier>\d+)/delete$",
        views.TierDelete.as_view(),
        name="tier.delete",
    ),
    re_path(
        r"^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/gultix_sponsors/sponsors/add$",
        views.SponsorCreate.as_view(),
        name="sponsor.add",
    ),
    re_path(
        r"^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/gultix_sponsors/sponsors/(?P<sponsor>\d+)/edit$",
        views.SponsorUpdate.as_view(),
        name="sponsor.edit",
    ),
    re_path(
        r"^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/gultix_sponsors/sponsors/(?P<sponsor>\d+)/move/(?P<direction>up|down)$",
        views.SponsorMove.as_view(),
        name="sponsor.move",
    ),
    re_path(
        r"^control/event/(?P<organizer>[^/]+)/(?P<event>[^/]+)/gultix_sponsors/sponsors/(?P<sponsor>\d+)/delete$",
        views.SponsorDelete.as_view(),
        name="sponsor.delete",
    ),
]
