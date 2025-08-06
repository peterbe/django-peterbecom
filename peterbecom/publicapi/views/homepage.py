from collections import defaultdict

from cachetools import TTLCache, cached
from django import http
from django.conf import settings
from django.db.models import Count
from django.utils import timezone
from django.views.decorators.cache import cache_page

from peterbecom.base.utils import json_response
from peterbecom.homepage.utils import make_categories_q
from peterbecom.plog.models import BlogComment, BlogItem, Category


@cached(cache=TTLCache(maxsize=1, ttl=60 * 10))
def get_category_id_name_map():
    mapping = {}
    for name, id in Category.objects.values_list("name", "id"):
        mapping[id] = name
    return mapping


@cache_page(10 if settings.DEBUG else 60 * 5, key_prefix="publicapi_cache_page")
def homepage_blogitems(request):
    context = {}
    try:
        page = int(request.GET.get("page") or "1")
        if page <= 0:
            raise ValueError()
    except ValueError:
        return http.HttpResponseBadRequest("invalid page")

    qs = BlogItem.objects.filter(pub_date__lt=timezone.now(), archived__isnull=True)

    ocs = request.GET.getlist("oc")
    if ocs:
        categories = []
        for oc in ocs:
            for id, name in get_category_id_name_map().items():
                if name.lower() == oc.lower():
                    # E.g. ?oc=web+Development
                    if name != oc:
                        return http.HttpResponsePermanentRedirect(f"/oc-{name}")
                    categories.append(id)
                    break
            else:
                return http.HttpResponseBadRequest(f"invalid oc {oc!r}")

        cat_q = make_categories_q(categories)
        qs = qs.filter(cat_q)

    if request.method == "HEAD":
        return http.HttpResponse("")

    try:
        batch_size = int(request.GET.get("size") or settings.HOMEPAGE_BATCH_SIZE)
        if batch_size > 20:
            raise ValueError("size must be less than 20")
        if batch_size <= 0:
            raise ValueError("size must be more than 0")
    except ValueError as exception:
        return http.HttpResponseBadRequest(str(exception))

    page = page - 1
    n, m = page * batch_size, (page + 1) * batch_size
    max_count = qs.count()
    if page * batch_size > max_count:
        return http.HttpResponseNotFound("Too far back in time")

    if (page + 1) * batch_size < max_count:
        context["next_page"] = page + 2
    else:
        context["next_page"] = None

    if page >= 1:
        context["previous_page"] = page
    else:
        context["previous_page"] = None

    blogitems = (qs.prefetch_related("categories").order_by("-pub_date"))[n:m]

    approved_comments_count = {}
    blog_comments_count_qs = (
        BlogComment.objects.filter(blogitem__in=blogitems, approved=True)
        .values("blogitem_id")
        .annotate(count=Count("blogitem_id"))
    )
    for count in blog_comments_count_qs:
        approved_comments_count[count["blogitem_id"]] = count["count"]

    context["posts"] = []

    category_names = get_category_id_name_map()

    categories = defaultdict(list)
    for (
        blogitem_id,
        category_id,
    ) in BlogItem.categories.through.objects.all().values_list(
        "blogitem_id", "category_id"
    ):
        categories[blogitem_id].append(category_names[category_id])

    def serialize_blogitem(blogitem):
        html_split = blogitem["text_rendered"].split("<!--split-->")
        if len(html_split) == 1:
            html, split = html_split[0], None
        else:
            html, split = html_split[0], len(html_split[1].strip())

        serialized = {
            "oid": blogitem["oid"],
            "title": blogitem["title"],
            "pub_date": blogitem["pub_date"],
            "comments": approved_comments_count.get(blogitem["id"]) or 0,
            "categories": categories[blogitem["id"]],
            "html": html,
            "url": blogitem["url"],
            "disallow_comments": blogitem["disallow_comments"],
            "split": split,
        }
        return serialized

    dedupe = set()
    for blogitem in blogitems.values(
        "id", "oid", "title", "pub_date", "text_rendered", "url", "disallow_comments"
    ):
        if blogitem["oid"] in dedupe:
            continue
        dedupe.add(blogitem["oid"])
        context["posts"].append(serialize_blogitem(blogitem))

    return json_response(context)
