from __future__ import absolute_import, unicode_literals
from celery import shared_task

import time

# from django.db.models import F

from .models import BlogItemHit, BlogItem


@shared_task
def sample_task():
    time.sleep(2)
    open('/tmp/sample_task.log', 'a').write('time:%s\n' % time.time())


@shared_task
def increment_blogitem_hit(oid):
    # BlogItemHits.objects.filter(oid=oid).update(hits=F('hits') + 1)
    # print('BlogItemHits {!r}'.format(oid))
    try:
        BlogItemHit.objects.create(blogitem=BlogItem.objects.get(oid=oid))
    except BlogItem.DoesNotExist:
        print("Can't find BlogItem with oid {!r}".format(oid))
