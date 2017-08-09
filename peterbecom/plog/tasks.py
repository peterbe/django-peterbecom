from __future__ import absolute_import, unicode_literals
from celery import shared_task

import time

from .models import BlogItemHit, BlogItem


@shared_task
def sample_task():
    time.sleep(2)
    open('/tmp/sample_task.log', 'a').write('time:%s\n' % time.time())


@shared_task
def increment_blogitem_hit(
    oid,
    http_user_agent=None,
    http_accept_language=None,
    remote_addr=None,
    http_referer=None,
):
    try:
        BlogItemHit.objects.create(
            blogitem=BlogItem.objects.get(oid=oid),
            http_user_agent=http_user_agent,
            http_accept_language=http_accept_language,
            http_referer=http_referer,
            remote_addr=remote_addr,
        )
    except BlogItem.DoesNotExist:
        print("Can't find BlogItem with oid {!r}".format(oid))
