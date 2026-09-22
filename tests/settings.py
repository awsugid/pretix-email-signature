"""
Isolated test settings: SQLite under a temporary DATA_DIR, locmem email
backend, dummy caches, no network access.

Usage: pytest tests --ds=tests.settings
"""

from pretix.testutils.settings import *  # NOQA

if "gultix_sponsors" not in INSTALLED_APPS:
    INSTALLED_APPS.append("gultix_sponsors")
