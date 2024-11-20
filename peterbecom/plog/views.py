import datetime
import logging

from django import http
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from .models import BlogItem, BlogItemHit

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


# Delete this method in late 2024
@require_http_methods(["PUT"])
@csrf_exempt
def blog_post_ping(request, oid, page=None):
    # Return a 410 Gone once the CDN is properly purged
    return http.JsonResponse({"deprecated": True})
    # user_agent = request.headers.get("User-Agent", "")
    # remote_addr = request.headers.get("x-forwarded-for") or request.META.get(
    #     "REMOTE_ADDR"
    # )
    # if not utils.is_bot(ua=user_agent, ip=remote_addr):
    #     http_referer = request.GET.get("referrer", request.headers.get("Referer"))
    #     if http_referer:
    #         current_url = request.build_absolute_uri().split("/ping")[0]
    #         if current_url == http_referer:
    #             http_referer = None
    #     increment_blogitem_hit(
    #         oid,
    #         remote_addr=remote_addr,
    #         http_referer=http_referer,
    #         page=page,
    #     )
    # return http.JsonResponse({"ok": True})


# @task()
# def increment_blogitem_hit(
#     oid,
#     remote_addr=None,
#     http_referer=None,
#     page=None,
# ):
#     if http_referer and len(http_referer) > 450:
#         http_referer = http_referer[: 450 - 3] + "..."
#     try:
#         blogitem_id = BlogItem.objects.values_list("id", flat=True).get(oid=oid)
#         BlogItemHit.objects.create(
#             blogitem_id=blogitem_id,
#             http_referer=http_referer,
#             remote_addr=remote_addr,
#             page=page,
#         )
#     except BlogItem.DoesNotExist:
#         print("Can't find BlogItem with oid {!r}".format(oid))


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


@ensure_csrf_cookie
def prepare_json(request):
    data = {"csrf_token": request.META["CSRF_COOKIE"]}
    return http.JsonResponse(data)


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
