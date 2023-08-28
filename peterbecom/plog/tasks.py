import datetime

from django.utils import timezone
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import send_mail
from django.template import loader
from huey import crontab
from huey.contrib.djhuey import periodic_task, task

from peterbecom.plog.models import (
    BlogComment,
    BlogItemDailyHits,
    BlogItemDailyHitsExistingError,
    BlogItemHit,
)


@task()
def send_new_comment_email(blogcomment_id):
    blogcomment = BlogComment.objects.get(id=blogcomment_id)
    tos = [x[1] for x in settings.MANAGERS]
    from_ = ["%s <%s>" % x for x in settings.MANAGERS][0]
    body = _get_comment_body(blogcomment.blogitem, blogcomment)
    subject = "Peterbe.com: New comment on '{}'".format(blogcomment.blogitem.title)
    send_mail(subject, body, from_, tos)


def _get_comment_body(blogitem, blogcomment):
    base_url = "https://%s" % Site.objects.get_current().domain
    if "peterbecom.local" in base_url:
        base_url = "http://localhost:4000"
    admin_url = base_url.replace("www.", "admin.")
    template = loader.get_template("plog/comment_body.txt")
    context = {
        "post": blogitem,
        "comment": blogcomment,
        "base_url": base_url,
        "admin_url": admin_url,
    }
    return template.render(context).strip()


@periodic_task(crontab(hour="*", minute="4"))
def run_populate_blogitem_daily_hits():
    date = timezone.now() - datetime.timedelta(days=1)
    try:
        sum_count, items_count = BlogItemDailyHits.rollup_date(date)
        print(f"Rolled up {items_count:,} blogitems a total of {sum_count:,} hits")
    except BlogItemDailyHitsExistingError:
        print(f"Already rolled up for {date}")


@periodic_task(crontab(hour="*", minute="8"))
def delete_old_blogitemhits():
    date = timezone.now() - datetime.timedelta(days=300)
    deleted = BlogItemHit.objects.filter(add_date__lt=date).delete()[0]
    print(f"Deleted {deleted:,} old BlogItemHit records older than {date}")
