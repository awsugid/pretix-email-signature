Gultix Sponsors
===============

This is a plugin for `pretix`_.

It shows sponsor advertisements in the footer of your event emails. Sponsors are
managed per event in ordered tiers with configurable logo widths, and the sponsor
footer is appended below the existing email signature (or below the body if no
signature is set). Emails without sponsors are sent unchanged.

This plugin only modifies emails sent with the event's selected mail renderer.

Requires pretix 2026.7 or above; tested with pretix 2026.7.0 on Python 3.13.

Usage
-----

1. Run the database migrations to create the sponsor tables (``pretix migrate``
   in the installed pretix environment) before starting web and worker processes.
2. Enable *Gultix Sponsors* in the 'plugins' tab of your event settings.
3. Select *Default with sponsors* as the event's mail renderer. Other renderers
   remain unchanged.
4. Add sponsor tiers with logo widths, upload sponsor logos, and publish the
   sponsors to show in the email footer.

Development setup
-----------------

1. Make sure that you have a working `pretix development setup`_.

2. Clone this repository.

3. Activate the virtual environment you use for pretix development.

4. Execute ``python setup.py develop`` within this directory to register this application with pretix's plugin registry.

5. Execute ``make`` within this directory to compile translations.

6. Restart your local pretix server. You can now use the plugin from this repository for your events by enabling it in
   the 'plugins' tab in the settings.

This plugin has CI set up to enforce a few code style rules. To check locally, you need these packages installed::

    pip install flake8 isort black

To check your plugin for rule violations, run::

    black --check .
    isort -c .
    flake8 .

You can auto-fix some of these issues by running::

    isort .
    black .

You can automatically check for these issues before you commit by running ``.install-hooks.sh``.


License
-------


Copyright 2026 Avei

Released under the terms of the Apache License 2.0



.. _pretix: https://github.com/pretix/pretix
.. _pretix development setup: https://docs.pretix.eu/en/latest/development/setup.html
