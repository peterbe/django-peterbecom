import logging

from django import http
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie

from .models import BlogItem

logger = logging.getLogger("plog.views")


ONE_HOUR = 60 * 60
ONE_DAY = ONE_HOUR * 24
ONE_WEEK = ONE_DAY * 7
ONE_MONTH = ONE_WEEK * 4
ONE_YEAR = ONE_WEEK * 52
THIS_YEAR = timezone.now().year


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
