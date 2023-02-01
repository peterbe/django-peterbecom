from django.apps import AppConfig


class PublicAPIConfig(AppConfig):
    name = "peterbecom.publicapi"

    def ready(self):
        # Implicitly connect a signal handlers decorated with @receiver.
        # from . import signals  # noqa: F401
        from .signals import run_all_now

        run_all_now()
