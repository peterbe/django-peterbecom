from __future__ import absolute_import
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "peterbecom.settings")

app = Celery("peterbecom")

# Using a string here means the worker don't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()


from django.conf import settings  # noqa


if "rollbar.contrib.django.middleware.RollbarNotifierMiddleware" in settings.MIDDLEWARE:
    import rollbar

    if not getattr(settings, "ROLLBAR", None):
        print("ROLLBAR not enabled for Celery")
    else:
        rollbar.init(**settings.ROLLBAR)

        def celery_base_data_hook(request, data):
            data["framework"] = "celery"

        rollbar.BASE_DATA_HOOK = celery_base_data_hook

        from celery.signals import task_failure

        @task_failure.connect
        def handle_task_failure(**kw):
            rollbar.report_exc_info(extra_data=kw)
