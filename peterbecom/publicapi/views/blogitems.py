from collections import defaultdict

from django import http
from django.conf import settings
from django.db.models import Count
from django.utils import timezone
from django.views.decorators.cache import cache_page

from peterbecom.plog.models import BlogComment, BlogItem, Category
from peterbecom.publicapi.forms import BlogitemsForm


@cache_page(10 if settings.DEBUG else 60 * 60, key_prefix="publicapi_cache_page")
def blogitems(request):

    form = BlogitemsForm(request.GET)
    if not form.is_valid():
        return http.HttpResponseBadRequest(str(form.errors))

    groups = defaultdict(list)
    now = timezone.now()
    group_dates = []

    _categories = Category.get_category_id_name_map()

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
        BlogComment.objects.filter(approved=True)
        .values("blogitem_id")
        .annotate(count=Count("blogitem_id"))
    )
    for count in blog_comments_count_qs:
        approved_comments_count[count["blogitem_id"]] = count["count"]

    qs = BlogItem.objects.filter(
        pub_date__lt=now,
        archived__isnull=True,
    )
    photos = form.cleaned_data.get("is_photo")
    if photos is not None:
        qs = qs.filter(is_photo=photos)

    for item in qs.values(
        "pub_date", "oid", "title", "pk", "open_graph_image"
    ).order_by("-pub_date"):
        group = item["pub_date"].strftime("%Y.%m")
        item["categories"] = blogitem_categories[item["pk"]]
        item["comments"] = approved_comments_count.get(item["pk"], 0)
        item["id"] = item.pop("pk")
        if photos is None:
            item.pop("open_graph_image", None)
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
