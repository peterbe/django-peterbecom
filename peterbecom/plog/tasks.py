from __future__ import absolute_import, unicode_literals
from celery import shared_task

import time
# from django.contrib.sites.models import Site

from .models import BlogItemHits


# site = Site.objects.get_current()
# base_url = 'https://%s' % site.domain


@shared_task
def sample_task():
    time.sleep(2)
    open('/tmp/sample_task.log', 'a').write('time:%s\n' % time.time())


@shared_task
def increment_blogitem_hit(oid):
    hits, created = BlogItemHits.objects.get_or_create(oid=oid)
    hits.hits += 1
    print "HIT %s => %d" % (oid, hits.hits)
    hits.save()
