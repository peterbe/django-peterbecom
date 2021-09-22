import datetime
from collections import defaultdict

from django import http
from django.db.models import Count
from django.utils import timezone

from peterbecom.plog.models import (
    BlogComment,
    BlogItem,
    Category,
)


def blogitems(request):
    groups = defaultdict(list)
    now = timezone.now()
    group_dates = []

    _categories = dict((x.pk, x.name) for x in Category.objects.all())
    blogitem_categories = defaultdict(list)
    for cat_item in BlogItem.categories.through.objects.all():
        blogitem_categories[cat_item.blogitem_id].append(
            _categories[cat_item.category_id]
        )

    approved_comments_count = {}
    blog_comments_count_qs = (
        BlogComment.objects.filter(blogitem__pub_date__lt=now, approved=True)
        .values("blogitem_id")
        .annotate(count=Count("blogitem_id"))
    )
    for count in blog_comments_count_qs:
        approved_comments_count[count["blogitem_id"]] = count["count"]

    for item in (
        BlogItem.objects.filter(pub_date__lt=now, archived__isnull=True)
        .values("pub_date", "oid", "title", "pk")
        .order_by("-pub_date")
    ):
        group = item["pub_date"].strftime("%Y.%m")
        item["categories"] = blogitem_categories[item["pk"]]
        item["comments"] = approved_comments_count.get(item["pk"], 0)
        groups[group].append(item)
        tup = (group, item["pub_date"].strftime("%B, %Y"))
        if tup not in group_dates:
            group_dates.append(tup)

    return http.JsonResponse({"groups": groups})


def blogpost(request, oid):
    try:
        blogitem = BlogItem.objects.get(oid__iexact=oid)
    except BlogItem.DoesNotExist:
        return http.HttpResponseNotFound(oid)

    future = timezone.now() + datetime.timedelta(days=10)
    if blogitem.pub_date > future:
        return http.HttpResponseNotFound("not published yet")
    if blogitem.archived:
        return http.HttpResponseNotFound("blog post archived")

    post = {
        "oid": blogitem.oid,
        "title": blogitem.title,
        "body": blogitem.text_rendered,
        "pub_date": blogitem.pub_date,
        "open_graph_image": blogitem.open_graph_image,
        "url": blogitem.url,
        "summary": blogitem.summary,
        "categories": [x.name for x in blogitem.categories.all()],
    }

    if blogitem.oid != "blogitem-040601-1":
        try:
            previous = blogitem.get_previous_by_pub_date(archived__isnull=True)
            post["previous_post"] = {"oid": previous.oid, "title": previous.title}
        except BlogItem.DoesNotExist:
            pass

        try:
            next = blogitem.get_next_by_pub_date(
                pub_date__lt=timezone.now(),
                archived__isnull=True,
            )
            post["next_post"] = {"oid": next.oid, "title": next.title}
        except BlogItem.DoesNotExist:
            pass

    comments = []
    return http.JsonResponse({"post": post, "comments": comments})
