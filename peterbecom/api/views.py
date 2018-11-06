import json
from functools import wraps

from django import http
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone

from peterbecom.plog.models import BlogItem, Category
from peterbecom.plog.views import PreviewValidationError, preview_by_data

# def bearer_token_required(view_func):
#     @wraps(view_func)
#     def inner(request, *args, **kwargs):
#         print("RIGHT HERE", request.META)
#         request.csrf_processing_done = True
#         raise PermissionDenied("No Bearer token")

#     return inner


# def api_login_required(view_func):
#     """similar to django.contrib.auth.decorators.login_required
#     except instead of redirecting it returns a 403 message if not
#     authenticated."""

#     @wraps(view_func)
#     def inner(request, *args, **kwargs):
#         if not request.user.is_active:
#             error_msg = "You are not logged in"
#             raise PermissionDenied(error_msg)
#         return view_func(request, *args, **kwargs)

#     return inner


def api_superuser_required(view_func):
    """Decorator that will return a 403 JSON response if the user
    is *not* a superuser.
    Use this decorator *after* others like api_login_required.
    """

    @wraps(view_func)
    def inner(request, *args, **kwargs):
        if not request.user.is_superuser:
            error_msg = "Must be superuser to access this view."
            raise PermissionDenied(error_msg)
        return view_func(request, *args, **kwargs)

    return inner


def _response(context, status=200, safe=False):
    return http.JsonResponse(context, status=status, safe=safe)


# @bearer_token_required
@api_superuser_required
def blogitems(request):
    if request.method == "POST":
        raise NotImplementedError

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


# @bearer_token_required
@api_superuser_required
def blogitem(request, oid):
    item = get_object_or_404(BlogItem, oid=oid)
    if request.method == "POST":
        raise NotImplementedError
        return
    context = {
        "blogitem": {
            "id": item.id,
            "oid": item.oid,
            "title": item.title,
            "pub_date": item.pub_date,
            "text": item.text,
            "keywords": item.proper_keywords,
            "categories": [{"id": x.id, "name": x.name} for x in item.categories.all()],
            "summary": item.summary,
            "url": item.summary,
            "display_format": item.display_format,
            "codesyntax": item.codesyntax,
            "disallow_comments": item.disallow_comments,
            "hide_comments": item.hide_comments,
            "modify_date": item.modify_date,
            "open_graph_image": item.open_graph_image,
            "_absolute_url": "/plog/{}".format(item.oid),
        }
    }
    return _response(context)


def categories(request):
    qs = (
        BlogItem.categories.through.objects.all()
        .values("category_id")
        .annotate(Count("category_id"))
        .order_by("-category_id__count")
    )
    all_categories = dict(Category.objects.all().values_list("id", "name"))
    context = {"categories": []}

    for count in qs:
        pk = count["category_id"]
        context["categories"].append(
            {"id": pk, "name": all_categories[pk], "count": count["category_id__count"]}
        )
    context["categories"].sort(key=lambda x: x["count"], reverse=True)

    return _response(context)


@api_superuser_required
def preview(request):
    assert request.method == "POST", request.method
    post_data = json.loads(request.body.decode("utf-8"))
    post_data["pub_date"] = timezone.now()
    try:
        html = preview_by_data(post_data, request)
    except PreviewValidationError as exception:
        form_errors, = exception.args
        context = {"blogitem": {"errors": str(form_errors)}}
        return _response(context)
    context = {"blogitem": {"html": html}}
    return _response(context)


def catch_all(request):
    if settings.DEBUG:
        raise http.Http404(request.path)
    return _response({"error": request.path}, status=404)
