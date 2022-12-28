import datetime
import logging
import re

from django import http
from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods, require_POST
from huey.contrib.djhuey import task

from peterbecom.base.utils import fake_ip_address

from . import utils
from .models import BlogComment, BlogItem, BlogItemHit
from .spamprevention import (
    contains_spam_patterns,
    contains_spam_url_patterns,
    is_trash_commenter,
)
from .tasks import send_new_comment_email
from .utils import render_comment_text

logger = logging.getLogger("plog.views")


ONE_HOUR = 60 * 60
ONE_DAY = ONE_HOUR * 24
ONE_WEEK = ONE_DAY * 7
ONE_MONTH = ONE_WEEK * 4
ONE_YEAR = ONE_WEEK * 52
THIS_YEAR = timezone.now().year


def blog_post(request, oid, page=None):
    if request.path.endswith("/ping"):
        # Sometimes this can happen when the URL parsing by Django
        # isn't working out.
        # E.g.
        # http://localhost:8000/plog/dont-forget-your-sets-in-python%0A/ping
        return blog_post_ping(request)

    return http.HttpResponse("Deprecated")


@require_http_methods(["PUT"])
@csrf_exempt
def blog_post_ping(request, oid, page=None):
    user_agent = request.headers.get("User-Agent", "")
    remote_addr = request.META.get("REMOTE_ADDR")
    if not utils.is_bot(ua=user_agent, ip=remote_addr):
        http_referer = request.GET.get("referrer", request.headers.get("Referer"))
        if http_referer:
            current_url = request.build_absolute_uri().split("/ping")[0]
            if current_url == http_referer:
                http_referer = None
        increment_blogitem_hit(
            oid,
            remote_addr=remote_addr,
            http_referer=http_referer,
            page=page,
        )
    return http.JsonResponse({"ok": True})


@task()
def increment_blogitem_hit(
    oid,
    remote_addr=None,
    http_referer=None,
    page=None,
):
    if http_referer and len(http_referer) > 450:
        http_referer = http_referer[: 450 - 3] + "..."
    try:
        blogitem_id = BlogItem.objects.values_list("id", flat=True).get(oid=oid)
        BlogItemHit.objects.create(
            blogitem_id=blogitem_id,
            http_referer=http_referer,
            remote_addr=remote_addr,
            page=page,
        )
    except BlogItem.DoesNotExist:
        print("Can't find BlogItem with oid {!r}".format(oid))


# legacy stuff
def all_blog_post_comments(request, oid):
    return redirect(f"/plog/{oid}", permanent=True)


def get_related_posts_by_keyword(post, limit=5, exclude_ids=None):
    if not post.proper_keywords:
        return BlogItem.objects.none()
    return (
        BlogItem.objects.filter(
            proper_keywords__overlap=post.proper_keywords,
            pub_date__lt=timezone.now(),
            archived__isnull=True,
        )
        .exclude(id=post.id)
        .exclude(id__in=exclude_ids or [])
        .order_by("-popularity")[:limit]
    )


def get_related_posts_by_categories(post, limit=5, exclude_ids=None):
    if not post.categories.all().exists():
        return BlogItem.objects.none()
    return (
        BlogItem.objects.filter(
            categories__in=post.categories.all(),
            pub_date__lt=timezone.now(),
            archived__isnull=True,
        )
        .distinct()
        .exclude(id=post.id)
        .exclude(id__in=exclude_ids or [])
        .order_by("-popularity")[:limit]
    )


def _render_comment(comment):
    return render_to_string("plog/comment.html", {"comment": comment})


@ensure_csrf_cookie
def prepare_json(request):
    data = {"csrf_token": request.META["CSRF_COOKIE"]}
    return http.JsonResponse(data)


@ensure_csrf_cookie
@require_POST
def preview_json(request):
    comment = request.POST.get("comment", "").strip()
    name = request.POST.get("name", "").strip()
    email = request.POST.get("email", "").strip()
    if not comment:
        return http.JsonResponse({})

    html = render_comment_text(comment.strip())
    comment = {
        "oid": "preview-oid",
        "name": name,
        "email": email,
        "rendered": html,
        "add_date": timezone.now(),
    }
    html = render_to_string("plog/comment.html", {"comment": comment, "preview": True})
    return http.JsonResponse({"html": html})


@require_POST
@transaction.atomic
def submit_json(request, oid):
    post = get_object_or_404(BlogItem, oid=oid, archived__isnull=True)
    if post.disallow_comments:
        return http.HttpResponseBadRequest("No comments please")
    comment = request.POST.get("comment", "").strip()
    if not comment:
        return http.HttpResponseBadRequest("Missing comment")

    # I'm desperate so I'll put in some easy-peasy spam checks before I get around
    # to building a proper classifier.
    comment_lower = comment.lower()
    if (
        (
            ("whatsapp" in comment_lower or "://" in comment)
            and ("@gmail.com" in comment_lower or "@yahoo.com" in comment_lower)
            and re.findall(r"\+\d+", comment)
        )
        or (
            ("@gmail.com" in comment_lower or "@yahoo.com" in comment_lower)
            and (
                "spell" in comment
                or "healing" in comment
                or "call doctor" in comment_lower
            )
        )
        or contains_spam_url_patterns(comment)
        or contains_spam_patterns(comment)
    ):
        return http.HttpResponseBadRequest("Looks too spammy")

    name = request.POST.get("name", "").strip()
    email = request.POST.get("email", "").strip()

    parent = request.POST.get("parent")
    if parent:
        parent = get_object_or_404(BlogComment, oid=parent)
    else:
        parent = None  # in case it was u''

    search = {"comment": comment}
    if name:
        search["name"] = name
    if email:
        search["email"] = email
    if parent:
        search["parent"] = parent

    ip_address = request.headers.get("x-forwarded-for") or request.META.get(
        "REMOTE_ADDR"
    )
    if ip_address == "127.0.0.1" and settings.FAKE_BLOG_COMMENT_IP_ADDRESS:
        ip_address = fake_ip_address(str(name) + str(email))

    user_agent = request.headers.get("User-Agent")

    if is_trash_commenter(
        name=name, email=email, ip_address=ip_address, user_agent=user_agent
    ):
        return http.JsonResponse({"trash": True}, status=400)

    for blog_comment in BlogComment.objects.filter(**search):
        break
    else:
        blog_comment = BlogComment.objects.create(
            oid=BlogComment.next_oid(),
            blogitem=post,
            parent=parent,
            approved=False,
            comment=comment,
            name=name,
            email=email,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        try:
            blog_comment.create_geo_lookup()
        except Exception as exception:
            if settings.DEBUG:
                raise
            print("WARNING! {!r} create_geo_lookup failed".format(exception))

        if post.oid != "blogitem-040601-1":
            transaction.on_commit(lambda: send_new_comment_email(blog_comment.id))

    html = render_to_string(
        "plog/comment.html", {"comment": blog_comment, "preview": True}
    )
    _comments = BlogComment.objects.filter(approved=True, blogitem=post)
    comment_count = _comments.count() + 1
    data = {
        "html": html,
        "parent": parent and parent.oid or None,
        "comment_count": comment_count,
    }

    return http.JsonResponse(data)


@cache_control(public=True, max_age=60 * 60 * 24 * 2)
def plog_index(request):
    return http.HttpResponse("Deprecated")


def plog_hits(request):
    raise NotImplementedError("Moved to adminui")


def plog_hits_data(request):
    hits = {}

    def get_count(start, end):
        return BlogItemHit.objects.filter(add_date__gte=start, add_date__lt=end).count()

    now = timezone.now()

    hits["last_hour"] = get_count(now - datetime.timedelta(hours=1), now)
    now = now.replace(hour=0, minute=0, second=0)
    hits["today"] = get_count(now - datetime.timedelta(days=1), now)
    hits["yesterday"] = get_count(
        now - datetime.timedelta(days=2), now - datetime.timedelta(days=1)
    )
    hits["last_week"] = get_count(
        now - datetime.timedelta(days=1 + 7), now - datetime.timedelta(days=7)
    )
    hits["last_month"] = get_count(
        now - datetime.timedelta(days=1 + 30), now - datetime.timedelta(days=30)
    )

    return http.JsonResponse({"hits": hits})
