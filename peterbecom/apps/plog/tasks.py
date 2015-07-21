import time
from django.conf import settings
from django.contrib.sites.models import Site
from celery.task import task


site = Site.objects.get(pk=settings.SITE_ID)
base_url = 'http://%s' % site.domain


@task()
def sample_task():
    time.sleep(2)
    open('/tmp/sample_task.log', 'a').write('time:%s\n' % time.time())
