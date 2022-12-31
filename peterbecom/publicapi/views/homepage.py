from collections import defaultdict

from django import http
from django.conf import settings
from django.db.models import Count
from django.utils import timezone
from django.views.decorators.cache import cache_page

from peterbecom.homepage.utils import make_categories_q
from peterbecom.plog.models import BlogComment, BlogItem, Category

_global_oc_cache = {}


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
            try:
                if _global_oc_cache.get(oc.lower()):
                    category = _global_oc_cache[oc.lower()]
                else:
                    category = Category.objects.get(name__iexact=oc)
                    _global_oc_cache[oc.lower()] = category
                categories.append(category)
                if category.name != oc:
                    return http.HttpResponsePermanentRedirect(f"/oc-{category.name}")
            except Category.DoesNotExist:
                return http.HttpResponseBadRequest(f"invalid oc {oc!r}")

        cat_q = make_categories_q(categories)
        qs = qs.filter(cat_q)

    if request.method == "HEAD":
        return http.HttpResponse("")

    batch_size = settings.HOMEPAGE_BATCH_SIZE
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

    category_names = {x["id"]: x["name"] for x in Category.objects.values("id", "name")}

    categories = defaultdict(list)
    for (
        blogitem_id,
        category_id,
    ) in BlogItem.categories.through.objects.all().values_list(
        "blogitem_id", "category_id"
    ):
        categories[blogitem_id].append(category_names[category_id])

    def serialize_blogitem(blogitem):
        serialized = {
            "oid": blogitem["oid"],
            "title": blogitem["title"],
            "pub_date": blogitem["pub_date"],
            "comments": approved_comments_count.get(blogitem["id"]) or 0,
            "categories": categories[blogitem["id"]],
            "html": blogitem["text_rendered"],
            "url": blogitem["url"],
            "disallow_comments": blogitem["disallow_comments"],
        }
        return serialized

    for blogitem in blogitems.values(
        "id", "oid", "title", "pub_date", "text_rendered", "url", "disallow_comments"
    ):
        context["posts"].append(serialize_blogitem(blogitem))

    return http.JsonResponse(context)
