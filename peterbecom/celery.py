from __future__ import absolute_import
import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'peterbecom.settings')

app = Celery('peterbecom')

# Using a string here means the worker don't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))

# app = Celery('peterbecom')
# app.config_from_object('django.conf:settings')
# app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

from django.conf import settings

if 'opbeat.contrib.django' in settings.INSTALLED_APPS:

    from opbeat.contrib.django.models import client, logger, register_handlers
    from opbeat.contrib.celery import register_signal

    try:
        register_signal(client)
    except Exception as e:
        logger.exception('Failed installing celery hook: %s' % e)

    register_handlers()
