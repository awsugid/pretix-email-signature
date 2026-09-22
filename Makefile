all: localecompile
LNGS:=`find gultix_sponsors/locale/ -mindepth 1 -maxdepth 1 -type d -printf "-l %f " 2>/dev/null || true`

localecompile:
	@if [ -d gultix_sponsors/locale ]; then django-admin compilemessages; else echo "No gultix_sponsors/locale directory, skipping compilemessages"; fi

localegen:
	django-admin makemessages --add-location file --keep-pot -i build -i dist -i "*egg*" $(LNGS)

.PHONY: all localecompile localegen
