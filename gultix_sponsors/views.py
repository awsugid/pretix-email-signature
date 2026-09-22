from django.contrib import messages
from django.db import transaction
from django.db.models import Prefetch
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView
from django.views.generic.edit import CreateView, UpdateView
from pretix.control.permissions import EventPermissionRequiredMixin
from pretix.control.views import (
    CreateView as EventCreateView,
    UpdateView as EventUpdateView,
)
from pretix.helpers.compat import CompatDeleteView

from .forms import SponsorForm, SponsorTierForm
from .models import Sponsor, SponsorTier


def _index_url(request):
    return reverse(
        "plugins:gultix_sponsors:index",
        kwargs={
            "organizer": request.event.organizer.slug,
            "event": request.event.slug,
        },
    )


class SponsorIndexView(EventPermissionRequiredMixin, TemplateView):
    permission = "event.settings.general:write"
    template_name = "gultix_sponsors/control/index.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["tiers"] = self.request.event.sponsor_tiers.prefetch_related(
            Prefetch(
                "sponsors",
                queryset=Sponsor.objects.order_by("position", "pk"),
            )
        ).order_by("position", "pk")
        return ctx


class SponsorFormViewMixin:
    permission = "event.settings.general:write"

    def form_invalid(self, form):
        messages.error(
            self.request, _("We could not save your changes. See below for details.")
        )
        return super().form_invalid(form)

    def get_success_url(self):
        return _index_url(self.request)


class TierCreate(SponsorFormViewMixin, EventPermissionRequiredMixin, CreateView):
    model = SponsorTier
    form_class = SponsorTierForm
    template_name = "gultix_sponsors/control/tier_form.html"
    permission = "event.settings.general:write"
    context_object_name = "sponsor_tier"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = SponsorTier(event=self.request.event)
        return kwargs

    @transaction.atomic
    def form_valid(self, form):
        form.instance.event = self.request.event
        messages.success(self.request, _("The sponsor tier has been created."))
        ret = super().form_valid(form)
        self.request.event.log_action(
            "gultix_sponsors.tier.added",
            user=self.request.user,
            data={"id": form.instance.pk, "name": form.instance.name},
        )
        return ret


class TierUpdate(SponsorFormViewMixin, EventPermissionRequiredMixin, UpdateView):
    model = SponsorTier
    form_class = SponsorTierForm
    template_name = "gultix_sponsors/control/tier_form.html"
    permission = "event.settings.general:write"
    context_object_name = "sponsor_tier"

    def get_object(self, queryset=None):
        try:
            return self.request.event.sponsor_tiers.get(pk=self.kwargs["tier"])
        except SponsorTier.DoesNotExist:
            raise Http404(_("The requested sponsor tier does not exist."))

    @transaction.atomic
    def form_valid(self, form):
        messages.success(self.request, _("Your changes have been saved."))
        ret = super().form_valid(form)
        self.request.event.log_action(
            "gultix_sponsors.tier.updated",
            user=self.request.user,
            data={"id": form.instance.pk, "name": form.instance.name},
        )
        return ret


class TierDelete(EventPermissionRequiredMixin, CompatDeleteView):
    model = SponsorTier
    template_name = "gultix_sponsors/control/delete_confirm.html"
    permission = "event.settings.general:write"
    extra_context = {"is_tier": True}

    def get_object(self, queryset=None):
        try:
            return self.request.event.sponsor_tiers.get(pk=self.kwargs["tier"])
        except SponsorTier.DoesNotExist:
            raise Http404(_("The requested sponsor tier does not exist."))

    @transaction.atomic
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        request.event.log_action(
            "gultix_sponsors.tier.deleted",
            user=request.user,
            data={"id": self.object.pk, "name": self.object.name},
        )
        self.object.delete()
        messages.success(request, _("The sponsor tier has been deleted."))
        return HttpResponseRedirect(success_url)

    def get_success_url(self):
        return _index_url(self.request)


class SponsorCreate(
    SponsorFormViewMixin, EventPermissionRequiredMixin, EventCreateView
):
    model = Sponsor
    form_class = SponsorForm
    template_name = "gultix_sponsors/control/sponsor_form.html"
    permission = "event.settings.general:write"
    context_object_name = "sponsor"

    def dispatch(self, request, *args, **kwargs):
        if not request.event.sponsor_tiers.exists():
            messages.error(request, _("Please create a sponsor tier first."))
            return redirect(_index_url(request))
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        tid = self.request.GET.get("tier")
        if tid and tid.isdigit():
            tier = self.request.event.sponsor_tiers.filter(pk=tid).first()
            if tier:
                initial["tier"] = tier
        return initial

    @transaction.atomic
    def form_valid(self, form):
        messages.success(self.request, _("The sponsor has been created."))
        ret = super().form_valid(form)
        self.request.event.log_action(
            "gultix_sponsors.sponsor.added",
            user=self.request.user,
            data={"id": form.instance.pk, "name": form.instance.name},
        )
        return ret


class SponsorUpdate(
    SponsorFormViewMixin, EventPermissionRequiredMixin, EventUpdateView
):
    model = Sponsor
    form_class = SponsorForm
    template_name = "gultix_sponsors/control/sponsor_form.html"
    permission = "event.settings.general:write"
    context_object_name = "sponsor"

    def get_object(self, queryset=None):
        try:
            return Sponsor.objects.get(
                tier__event=self.request.event, pk=self.kwargs["sponsor"]
            )
        except Sponsor.DoesNotExist:
            raise Http404(_("The requested sponsor does not exist."))

    @transaction.atomic
    def form_valid(self, form):
        messages.success(self.request, _("Your changes have been saved."))
        ret = super().form_valid(form)
        self.request.event.log_action(
            "gultix_sponsors.sponsor.updated",
            user=self.request.user,
            data={"id": form.instance.pk, "name": form.instance.name},
        )
        return ret


class SponsorDelete(EventPermissionRequiredMixin, CompatDeleteView):
    model = Sponsor
    template_name = "gultix_sponsors/control/delete_confirm.html"
    permission = "event.settings.general:write"

    def get_object(self, queryset=None):
        try:
            return Sponsor.objects.get(
                tier__event=self.request.event, pk=self.kwargs["sponsor"]
            )
        except Sponsor.DoesNotExist:
            raise Http404(_("The requested sponsor does not exist."))

    @transaction.atomic
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        request.event.log_action(
            "gultix_sponsors.sponsor.deleted",
            user=request.user,
            data={"id": self.object.pk, "name": self.object.name},
        )
        self.object.delete()
        messages.success(request, _("The sponsor has been deleted."))
        return HttpResponseRedirect(success_url)

    def get_success_url(self):
        return _index_url(self.request)
