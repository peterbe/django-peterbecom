from collections import defaultdict

from django import http
from django.conf import settings
from django.db.models import Count
from django.utils import timezone
from django.views.decorators.cache import cache_page

from peterbecom.plog.models import BlogComment, BlogItem, Category


@cache_page(10 if settings.DEBUG else 60 * 5, key_prefix="publicapi_cache_page")
def blogitems(request):
    groups = defaultdict(list)
    now = timezone.now()
    group_dates = []

    _categories = {x["id"]: x["name"] for x in Category.objects.values("id", "name")}

    blogitem_categories = defaultdict(list)
    for (
        blogitem_id,
        category_id,
    ) in BlogItem.categories.through.objects.all().values_list(
        "blogitem_id", "category_id"
    ):
        blogitem_categories[blogitem_id].append(_categories[category_id])

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
        item["id"] = item.pop("pk")
        groups[group].append(item)
        tup = (group, item["pub_date"].strftime("%B, %Y"))
        if tup not in group_dates:
            group_dates.append(tup)

    groups_list = []
    for key in groups:
        groups_list.append(
            {
                "date": key,
                "posts": groups[key],
            }
        )

    return http.JsonResponse({"groups": groups_list})
