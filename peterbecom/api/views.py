import datetime
import os
import re
import json
from functools import wraps
from urllib.parse import urlparse

from django import http

from django.db.models import Count, Q
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Min, Max, Avg

from peterbecom.base.models import PostProcessing
from peterbecom.plog.models import BlogItem, Category, BlogFile
from peterbecom.plog.views import PreviewValidationError, preview_by_data
from .forms import EditBlogForm, BlogFileUpload
from peterbecom.base.templatetags.jinja_helpers import thumbnail


def api_superuser_required(view_func):
    """Decorator that will return a 403 JSON response if the user
    is *not* a superuser.
    Use this decorator *after* others like api_login_required.
    """

    @wraps(view_func)
    def inner(request, *args, **kwargs):
        if not request.user.is_superuser:
            error_msg = "Must be superuser to access this view."
            # raise PermissionDenied(error_msg)
            return http.JsonResponse({"error": error_msg}, status=403)
        return view_func(request, *args, **kwargs)

    return inner


def _response(context, status=200, safe=False):
    return http.JsonResponse(context, status=status, safe=safe)


@api_superuser_required
def blogitems(request):
    if request.method == "POST":
        data = json.loads(request.body.decode("utf-8"))
        data["proper_keywords"] = data.pop("keywords")
        form = EditBlogForm(data)
        if form.is_valid():
            item = form.save()
            assert item._render(refresh=True)
            context = {"blogitem": {"id": item.id, "oid": item.oid}}
            return _response(context, status=201)
        else:
            return _response({"errors": form.errors}, status=400)

    def _serialize_blogitem(item):
        return {
            "id": item.id,
            "oid": item.oid,
            "title": item.title,
            "pub_date": item.pub_date,
            "_is_published": item.pub_date < timezone.now(),
            "modify_date": item.modify_date,
            "categories": [{"id": x.id, "name": x.name} for x in item.categories.all()],
            "keywords": item.proper_keywords,
            "summary": item.summary,
        }

    page = int(request.GET.get("page", 1))
    batch_size = int(request.GET.get("batch_size", 25))
    search = request.GET.get("search", "").lower().strip()
    items = BlogItem.objects.all()

    order_by = request.GET.get("order", "modify_date")
    assert order_by in ("modify_date", "pub_date"), order_by
    items = items.order_by("-" + order_by)
    if search:
        items = items.filter(Q(title__icontains=search) | Q(oid__icontains=search))
    items = items.prefetch_related("categories")
    context = {"blogitems": []}
    n, m = ((page - 1) * batch_size, page * batch_size)
    for item in items[n:m]:
        context["blogitems"].append(_serialize_blogitem(item))
    context["count"] = items.count()
    return _response(context)


@api_superuser_required
def blogitem(request, oid):
    item = get_object_or_404(BlogItem, oid=oid)
    if request.method == "POST":
        data = json.loads(request.body.decode("utf-8"))
        data["proper_keywords"] = data.pop("keywords")
        form = EditBlogForm(data, instance=item)
        if form.is_valid():
            form.save()
            item.refresh_from_db()
            assert item._render(refresh=True)
        else:
            return _response({"errors": form.errors}, status=400)

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
            "url": item.url,
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


@api_superuser_required
def open_graph_image(request, oid):
    blogitem = get_object_or_404(BlogItem, oid=oid)

    context = {"images": []}

    images_used = re.findall(r'<a href="(.*?)"', blogitem.text)
    images_used = [
        x
        for x in images_used
        if x.lower().endswith(".png") or x.lower().endswith(".jpg")
    ]
    images_used.extend(re.findall(r'<img src="(.*?)"', blogitem.text))
    images_used_paths = [urlparse(x).path for x in images_used]
    options = []
    for i, image in enumerate(_post_thumbnails(blogitem)):
        # from pprint import pprint
        # pprint(image)
        full_url_path = image["full_url"]
        if "://" in full_url_path:
            full_url_path = urlparse(full_url_path).path

        options.append(
            {
                "label": "Thumbnail #{}".format(i + 1),
                "src": image["full_url"],
                "size": image["full_size"],
                "current": (
                    blogitem.open_graph_image
                    and image["full_url"] == blogitem.open_graph_image
                ),
                "used_in_text": full_url_path in images_used_paths,
            }
        )

    if request.method == "POST":
        post = json.loads(request.body.decode("utf-8"))
        src = post.get("src")
        if not src or src not in [x["src"] for x in options]:
            return http.HttpResponseBadRequest("No src")
        if blogitem.open_graph_image and blogitem.open_graph_image == src:
            blogitem.open_graph_image = None
        else:
            blogitem.open_graph_image = src
        blogitem.save()
        return _response({"ok": True})

    context["images"] = options
    return _response(context)


@api_superuser_required
def images(request, oid):
    blogitem = get_object_or_404(BlogItem, oid=oid)

    context = {"images": _post_thumbnails(blogitem)}

    if request.method == "POST":
        form = BlogFileUpload(
            dict(
                request.POST, blogitem=blogitem.id, title=request.POST.get("title", "")
            ),
            request.FILES,
        )
        if form.is_valid():
            instance = form.save()
            return _response({"id": instance.id})
        return _response({"errors": form.errors}, status=400)
    elif request.method == "DELETE":
        blogfile = get_object_or_404(BlogFile, blogitem=blogitem, id=request.GET["id"])
        blogfile.delete()
        return _response({"deleted": True})
    return _response(context)


def _post_thumbnails(blogitem):
    blogfiles = BlogFile.objects.filter(blogitem=blogitem).order_by("add_date")

    images = []

    for blogfile in blogfiles:
        if not os.path.isfile(blogfile.file.path):
            continue
        full_im = thumbnail(blogfile.file, "1000x1000", upscale=False, quality=100)
        full_url = full_im.url
        image = {"full_url": full_url, "full_size": full_im.size}
        formats = (
            ("small", "120x120"),
            ("big", "230x230"),
            ("bigger", "370x370"),  # iPhone 6 is 375
        )
        for key, geometry in formats:
            im = thumbnail(blogfile.file, geometry, quality=81)
            url_ = im.url
            image[key] = {
                "url": url_,
                "alt": getattr(blogfile, "title", blogitem.title),
                "width": im.width,
                "height": im.height,
            }
        images.append(image)
    return images


@api_superuser_required
def postprocessings(request):

    context = {
        "statistics": _postprocessing_statistics(),
        "records": _postprocessing_records(),
    }

    return _response(context)


def _postprocessing_statistics():

    context = {"groups": []}

    base_qs = PostProcessing.objects.filter(duration__isnull=False)

    ongoing = PostProcessing.ongoing().count()
    last24h = base_qs.filter(
        created__gte=timezone.now() - datetime.timedelta(days=1)
    ).count()
    last1h = base_qs.filter(
        created__gte=timezone.now() - datetime.timedelta(seconds=3600)
    ).count()
    last7d = base_qs.filter(
        created__gte=timezone.now() - datetime.timedelta(days=1)
    ).count()

    def fmt(x):
        return format(x, ",")

    context["groups"].append(
        {
            "label": "Counts",
            "key": "counts",
            "items": [
                {"key": "ongoing", "label": "Ongoing", "value": fmt(ongoing)},
                {"key": "last1h", "label": "Last 1h", "value": fmt(last1h)},
                {"key": "last24h", "label": "Last 24h", "value": fmt(last24h)},
                {"key": "last7d", "label": "Last 7 days", "value": fmt(last7d)},
            ],
        }
    )

    def fmt_seconds(s):
        return "{:.1f}".format(s)

    try:
        last, = base_qs.filter(exception__isnull=True).order_by("-created")[:1]
        last_duration = last.duration
        context["groups"].append(
            {
                "label": "Rates (seconds)",
                "key": "rates",
                "items": [
                    {
                        "key": "last",
                        "label": "Last one",
                        "value": fmt_seconds(last_duration.total_seconds()),
                    }
                ],
            }
        )
    except ValueError:
        last = None

    avg7d = base_qs.filter(
        exception__isnull=True, created__gte=timezone.now() - datetime.timedelta(days=7)
    ).aggregate(duration=Avg("duration"))["duration"]
    if avg7d:
        context["groups"][-1]["items"].append(
            {
                "key": "avg7d",
                "label": "Avg (7d)",
                "value": fmt_seconds(avg7d.total_seconds()),
            }
        )

    best7d = base_qs.filter(
        exception__isnull=True, created__gte=timezone.now() - datetime.timedelta(days=7)
    ).aggregate(duration=Min("duration"))["duration"]
    if best7d:
        context["groups"][-1]["items"].append(
            {
                "key": "best7d",
                "label": "Best (7d)",
                "value": fmt_seconds(best7d.total_seconds()),
            }
        )

    worst7d = base_qs.filter(
        exception__isnull=True, created__gte=timezone.now() - datetime.timedelta(days=7)
    ).aggregate(duration=Max("duration"))["duration"]
    if worst7d:
        context["groups"][-1]["items"].append(
            {
                "key": "worst7d",
                "label": "Worst (7d)",
                "value": fmt_seconds(worst7d.total_seconds()),
            }
        )

    return context


def _postprocessing_records(limit=10):
    records = []

    def serialize_record(each):
        return {
            "id": each.id,
            "url": each.url,
            "filepath": each.filepath,
            "duration": each.duration and each.duration.total_seconds() or None,
            "exception": each.exception,
            "notes": each.notes and each.notes or [],
            "created": each.created,
            "_previous": None,
        }

    for each in PostProcessing.objects.order_by("-created")[:limit]:
        record = serialize_record(each)
        if each.previous:
            record["_previous"] = serialize_record(each.previous)
        records.append(record)

    return records
