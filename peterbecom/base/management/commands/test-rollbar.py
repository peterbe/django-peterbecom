import rollbar
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def handle(self, **options):
        ROLLBAR_ENABLED = settings.ROLLBAR and settings.ROLLBAR.get("enabled", True)
        if ROLLBAR_ENABLED:
            redacted = (
                settings.ROLLBAR["access_token"][:4]
                + "..."
                + settings.ROLLBAR["access_token"][-4:]
            )
            self.stdout.write(
                self.style.WARNING(f"ROLLBAR is enabled access token {redacted!r}")
            )
            rollbar.init(
                settings.ROLLBAR["access_token"], settings.ROLLBAR["environment"]
            )
            uuid = rollbar.report_message("testing rollbar")
            self.stdout.write(self.style.SUCCESS(f"Reported message with UUID {uuid}"))
        elif not settings.ROLLBAR:
            self.stdout.write(self.style.ERROR("settings.ROLLBAR not defined"))
        elif not settings.ROLLBAR.get("enabled", True):
            self.stdout.write(self.style.ERROR("settings.ROLLBAR.enabled is falsy"))
