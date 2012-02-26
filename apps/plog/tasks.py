import time
import logging
from akismet import Akismet
from django.conf import settings
from apps.plog.models import BlogComment
from django.contrib.sites.models import Site
from celery.task import task


site = Site.objects.get(pk=settings.SITE_ID)
base_url = 'http://%s' % site.domain

akismet_api = Akismet(agent=settings.AKISMET_USERAGENT)
akismet_api.setAPIKey(key=settings.AKISMET_KEY, blog_url=base_url)


@task()
def akismet_rate(pk):
    try:
        blog_comment = BlogComment.objects.get(pk=pk)
    except BlogComment.DoesNotExist:
        # could just be that the transaction hasn't completed yet
        time.sleep(1)
        try:
            blog_comment = BlogComment.objects.get(pk=pk)
        except BlogComment.DoesNotExist:
            logging.error("Unable to find BlogComment with pk=%r" % pk)
            return

    logging.debug("Using base URL %r for Akisment" % base_url)
    if not akismet_api.verify_key():
        logging.warn("Unable aquire a real Akisment key")
    else:
        data = {
            'user_ip': blog_comment.ip_address,
            'user_agent': blog_comment.user_agent,
            'comment_author': blog_comment.name,
            'comment_author_email': blog_comment.email,
          }
        comment = blog_comment.comment.encode('utf-8')
        is_spam = akismet_api.comment_check(comment, data)
        if is_spam:
            logging.info("Akisment thinks %r is spam (%r)" % (
              blog_comment, blog_comment.comment[:50]
            ))
        else:
            logging.info("Akisment thinks %r is NOT spam" % (
              blog_comment,
            ))
        blog_comment.akisment_pass = is_spam
        blog_comment.save()


@task()
def sample_task():
    time.sleep(2)
    open('/tmp/sample_task.log','a').write('time:%s\n'time.time())
