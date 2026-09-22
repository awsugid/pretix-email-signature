from django.utils.translation import gettext_lazy

from . import __version__

try:
    from pretix.base.plugins import PluginConfig
except ImportError:
    raise RuntimeError("Please use pretix 2026.7 or above to run this plugin!")


class PluginApp(PluginConfig):
    default = True
    name = "gultix_sponsors"
    verbose_name = "Gultix Sponsors"

    class PretixPluginMeta:
        name = gettext_lazy("Gultix Sponsors")
        author = "Avei"
        description = gettext_lazy("Show sponsor logos below the email signature")
        visible = True
        version = __version__
        category = "CUSTOMIZATION"
        compatibility = "pretix>=2026.7.0"
        settings_links = []
        navigation_links = []

    def ready(self):
        from . import signals  # NOQA
