from django import http
from django.db.models import Q

from peterbecom.plog.models import BlogItem, Category


def _response(context, status=200, safe=False):
    return http.JsonResponse(context, status=status, safe=safe)


def blogitems(request):
    if request.method == "POST":
        raise NotImplementedError

    page = int(request.GET.get("page", 1))
    batch_size = int(request.GET.get("batch_size", 25))
    search = request.GET.get("search", "").lower().strip()
    items = BlogItem.objects.all().order_by("-modify_date")
    if search:
        items = items.filter(Q(title__icontains=search) | Q(oid__icontains=search))
    items = items.prefetch_related("categories")
    context = {"blogitems": []}
    n, m = ((page - 1) * batch_size, page * batch_size)
    for item in items[n:m]:
        context["blogitems"].append(_serialize_blogitem(item))
    context["count"] = items.count()
    return _response(context)


def _serialize_blogitem(item):
    return {
        "id": item.id,
        "oid": item.oid,
        "title": item.title,
        "pub_date": item.pub_date,
        "modify_date": item.modify_date,
        "categories": [{"id": x.id, "name": x.name} for x in item.categories.all()],
        "keywords": item.proper_keywords,
    }


def categories(request):
    context = {
        "categories": [
            {"id": x.id, "name": x.name}
            for x in Category.objects.all().order_by("name")
        ]
    }
    return _response(context)
