import datetime
import textwrap

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import send_mail
from django.utils import timezone
from huey import crontab
from huey.contrib.djhuey import periodic_task, task

from peterbecom.plog.models import (
    BlogComment,
    BlogItem,
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
    subject = f"Peterbe.com: New comment on {blogcomment.blogitem.title!r}"
    send_mail(subject, body, from_, tos)


def _get_comment_body(blogitem, blogcomment):
    base_url = "https://%s" % Site.objects.get_current().domain
    if "peterbecom.local" in base_url:
        base_url = "http://localhost:4000"
    admin_url = base_url.replace("www.", "admin.")
    absolute_url = f"{base_url}{blogitem.get_absolute_url()}#{blogcomment.oid}"
    return f"""
Post: {blogitem.title}
{absolute_url}

Name: {blogcomment.name}
Email: {blogcomment.email}
IP Address: {blogcomment.ip_address}
User Agent: {blogcomment.user_agent}
Comment:
{line_indent(blogcomment.comment)}

{admin_url}/plog/comments#search={blogcomment.oid}
    """.strip()


def line_indent(text, indent=" " * 4):
    return "\n".join(
        textwrap.wrap(text, initial_indent=indent, subsequent_indent=indent)
    )


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


@periodic_task(
    # Every hour in local dev
    crontab(hour="*", minute="0")
    if settings.DEBUG
    # Every day at midnight in production
    else crontab(hour="0", minute="0")
)
def reindex_search_terms():
    count, took = BlogItem.index_all_search_terms()
    print(f"Indexed {count:,} search terms in {took:.1f} seconds ({timezone.now()})")
