import datetime
import json
import os
import re
import statistics
from collections import defaultdict
from functools import lru_cache, wraps
from urllib.parse import urlparse

import requests
from django import http
from django.conf import settings
from django.contrib.gis.geoip2 import GeoIP2
from django.core.cache import cache
from django.db.models import Avg, Count, Max, Min, Q
from django.shortcuts import get_object_or_404
from django.template import Context
from django.template.loader import get_template
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from geoip2.errors import AddressNotFoundError
from keycdn import keycdn  # https://github.com/keycdn/python-keycdn-api/issues/4

from peterbecom.awspa.models import AWSProduct
from peterbecom.awspa.search import search as awspa_search
from peterbecom.awspa.templatetags.jinja_helpers import awspa_product
from peterbecom.base.models import PostProcessing, SearchResult
from peterbecom.base.templatetags.jinja_helpers import thumbnail
from peterbecom.plog.models import (
    BlogComment,
    BlogFile,
    BlogItem,
    BlogItemHit,
    Category,
)
from peterbecom.plog.utils import rate_blog_comment, valid_email  # move this some day

from .forms import (
    BlogCommentBatchForm,
    BlogFileUpload,
    BlogitemRealtimeHitsForm,
    EditBlogCommentForm,
    EditBlogForm,
    PreviewBlogForm,
)
from .tasks import send_comment_reply_email


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
    items = _amend_blogitems_search(items, search)

    items = items.prefetch_related("categories")
    context = {"blogitems": []}
    n, m = ((page - 1) * batch_size, page * batch_size)
    for item in items[n:m]:
        context["blogitems"].append(_serialize_blogitem(item))
    context["count"] = items.count()
    return _response(context)


def _amend_blogitems_search(qs, search):
    if search:
        category_names = []
        cat_regex = re.compile(r"(cat:\s*([\w\s]+))")
        for found in cat_regex.findall(search):
            category_names.append(found[1])
            search = cat_regex.sub("", search).strip().strip(",")
        if category_names:
            q = Q()
            for name in category_names:
                q |= Q(name__iexact=name)
            categories = Category.objects.filter(q)
            cat_q = Q()
            for category in categories:
                cat_q |= Q(categories=category)
            qs = qs.filter(cat_q)

    if search:
        qs = qs.filter(Q(title__icontains=search) | Q(oid__icontains=search))
    return qs


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
            "awsproducts_count": AWSProduct.objects.exclude(disabled=True)
            .filter(keyword__in=item.get_all_keywords())
            .count(),
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


class PreviewValidationError(Exception):
    """When something is wrong with the preview data."""


@api_superuser_required
def preview(request):
    assert request.method == "POST", request.method
    post_data = json.loads(request.body.decode("utf-8"))
    post_data["pub_date"] = timezone.now()
    try:
        html = preview_by_data(post_data, request)
    except PreviewValidationError as exception:
        form_errors, = exception.args
        context = {"blogitem": {"errors": form_errors}}
        return _response(context)
    context = {"blogitem": {"html": html}}
    return _response(context)


def preview_by_data(data, request):
    post_data = {}
    for key, value in data.items():
        if value:
            post_data[key] = value
    post_data["oid"] = "doesntmatter"
    post_data["keywords"] = []
    form = PreviewBlogForm(data=post_data)
    if not form.is_valid():
        raise PreviewValidationError(form.errors)

    class MockPost(object):
        def count_comments(self):
            return 0

        @property
        def rendered(self):
            return BlogItem.render(
                self.text, self.display_format, self.codesyntax, strict=True
            )

    post = MockPost()
    post.title = form.cleaned_data["title"]
    post.text = form.cleaned_data["text"]
    post.display_format = form.cleaned_data["display_format"]
    post.codesyntax = form.cleaned_data["codesyntax"]
    post.url = form.cleaned_data["url"]
    post.pub_date = form.cleaned_data["pub_date"]
    post.categories = Category.objects.filter(pk__in=form.cleaned_data["categories"])
    template = get_template("plog/_post.html")
    context = Context({"post": post, "request": request})
    return template.render(context)


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
        full_im = thumbnail(blogfile.file, "2000x2000", upscale=False, quality=100)
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
def awspa(request, oid):
    blogitem = get_object_or_404(BlogItem, oid=oid)

    if request.method == "POST":
        if request.POST.get("keyword"):
            keyword = request.POST["keyword"]
            searchindex = request.POST["searchindex"]
            load_more_awsproducts(keyword, searchindex)
        else:
            id = request.POST["id"]
            awsproduct = get_object_or_404(AWSProduct, id=id)
            awsproduct.disabled = not awsproduct.disabled
            awsproduct.save()
    elif request.method == "DELETE":
        id = request.GET["id"]
        awsproduct = get_object_or_404(AWSProduct, id=id)
        awsproduct.delete()

    context = {"products": {}}
    all_keywords = blogitem.get_all_keywords()
    context["products"] = defaultdict(list)
    for keyword in all_keywords:
        qs = AWSProduct.objects.filter(keyword__iexact=keyword)
        recently = timezone.now() - datetime.timedelta(seconds=60)
        for product in qs.order_by("disabled", "-modify_date"):
            context["products"][keyword].append(
                {
                    "html": awspa_product(product),
                    "id": product.id,
                    "searchindex": product.searchindex,
                    "asin": product.asin,
                    "disabled": product.disabled,
                    "title": product.title,
                    "add_date": product.add_date,
                    "modify_date": product.modify_date,
                    "_new": product.add_date > recently,
                }
            )

    return _response(context)


class AWSPAError(Exception):
    """happens when we get a Product Links API error"""


def load_more_awsproducts(keyword, searchindex):
    items, error = awspa_search(keyword, searchindex=searchindex, sleep=1)
    if error:
        raise AWSPAError(error)

    keyword = keyword.lower()

    new = []

    for item in items:
        item.pop("ImageSets", None)
        # print('=' * 100)
        # pprint(item)
        asin = item["ASIN"]
        title = item["ItemAttributes"]["Title"]
        if not item["ItemAttributes"].get("ListPrice"):
            print("SKIPPING BECAUSE NO LIST PRICE")
            print(item)
            continue
        if not item.get("MediumImage"):
            print("SKIPPING BECAUSE NO MEDIUM IMAGE")
            print(item)
            continue
        try:
            awsproduct = AWSProduct.objects.get(
                asin=asin, keyword=keyword, searchindex=searchindex
            )
            awsproduct.title = title
            awsproduct.payload = item
            awsproduct.save()
        except AWSProduct.DoesNotExist:
            awsproduct = AWSProduct.objects.create(
                asin=asin,
                title=title,
                payload=item,
                keyword=keyword,
                searchindex=searchindex,
                disabled=True,
            )
            new.append(awsproduct)

    return new


@api_superuser_required
def postprocessings(request):

    context = {
        "statistics": _postprocessing_statistics(request.GET),
        "records": _postprocessing_records(request.GET),
    }

    return _response(context)


def _postprocessing_statistics(request_GET):

    context = {"groups": []}

    base_qs = PostProcessing.objects.filter(duration__isnull=False)
    base_qs = _filter_postprocessing_queryset(base_qs, request_GET)

    ongoing = (
        PostProcessing.ongoing()
        .filter(created__gte=timezone.now() - datetime.timedelta(seconds=3600))
        .count()
    )
    last24h = base_qs.filter(
        created__gte=timezone.now() - datetime.timedelta(days=1)
    ).count()
    last1h = base_qs.filter(
        created__gte=timezone.now() - datetime.timedelta(seconds=3600)
    ).count()
    last7d = base_qs.filter(
        created__gte=timezone.now() - datetime.timedelta(days=7)
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


def _postprocessing_records(request_GET, limit=10):
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

    qs = PostProcessing.objects.all()
    qs = _filter_postprocessing_queryset(qs, request_GET)

    for each in qs.order_by("-created")[:limit]:
        record = serialize_record(each)
        if each.previous:
            record["_previous"] = serialize_record(each.previous)
        records.append(record)

    return records


def _filter_postprocessing_queryset(qs, request_GET):
    q = request_GET.get("q")
    duration_regex = re.compile(r"duration:?\s*(>|<)\s*([\d\.]+)s?")
    if q:
        duration = re.findall(duration_regex, q)
        if duration:
            operator, seconds = duration[0]
            seconds = float(seconds)
            if operator == ">":
                qs = qs.filter(duration__gt=datetime.timedelta(seconds=seconds))
            else:
                qs = qs.filter(duration__lt=datetime.timedelta(seconds=seconds))
            q = duration_regex.sub("", q)

        technique = qs.filter
        if q.startswith("!"):
            q = q[1:]
            technique = qs.exclude
        if q.endswith("$"):
            qs = technique(url__endswith=q[:-1])
        elif q:
            qs = technique(url__contains=q)
    return qs


@api_superuser_required
def searchresults(request):

    context = {
        "statistics": _searchresults_statistics(request.GET),
        "records": _searchresults_records(request.GET),
    }

    return _response(context)


def _searchresults_statistics(request_GET):

    context = {"groups": []}

    base_qs = SearchResult.objects.all()

    last24h = base_qs.filter(
        created__gte=timezone.now() - datetime.timedelta(days=1)
    ).count()
    last7d = base_qs.filter(
        created__gte=timezone.now() - datetime.timedelta(days=7)
    ).count()
    last30d = base_qs.filter(
        created__gte=timezone.now() - datetime.timedelta(days=30)
    ).count()
    ever = base_qs.count()

    def fmt(x):
        return format(x, ",")

    context["groups"].append(
        {
            "label": "Counts",
            "key": "counts",
            "items": [
                {"key": "last24h", "label": "Last 24h", "value": fmt(last24h)},
                {"key": "last7d", "label": "Last 7 days", "value": fmt(last7d)},
                {"key": "last30d", "label": "Last 30 days", "value": fmt(last30d)},
                {"key": "ever", "label": "Ever", "value": fmt(ever)},
            ],
        }
    )

    def fmt_seconds(s):
        return "{:.1f}".format(s * 1000)

    try:
        last, = base_qs.order_by("-created")[:1]
        context["groups"].append(
            {
                "label": "Rates (milliseconds)",
                "key": "rates",
                "items": [
                    {
                        "key": "last",
                        "label": "Last one",
                        "value": fmt_seconds(last.search_time.total_seconds()),
                    }
                ],
            }
        )
    except ValueError:
        last = None

    avg30d = base_qs.filter(
        created__gte=timezone.now() - datetime.timedelta(days=30)
    ).aggregate(search_time=Avg("search_time"))["search_time"]
    if avg30d:
        context["groups"][-1]["items"].append(
            {
                "key": "avg30d",
                "label": "Avg (30d)",
                "value": fmt_seconds(avg30d.total_seconds()),
            }
        )

    best30d = base_qs.filter(
        created__gte=timezone.now() - datetime.timedelta(days=30)
    ).aggregate(search_time=Min("search_time"))["search_time"]
    if best30d:
        context["groups"][-1]["items"].append(
            {
                "key": "best30d",
                "label": "Best (30d)",
                "value": fmt_seconds(best30d.total_seconds()),
            }
        )

    worst30d = base_qs.filter(
        created__gte=timezone.now() - datetime.timedelta(days=30)
    ).aggregate(search_time=Max("search_time"))["search_time"]
    if worst30d:
        context["groups"][-1]["items"].append(
            {
                "key": "worst30d",
                "label": "Worst (30d)",
                "value": fmt_seconds(worst30d.total_seconds()),
            }
        )

    return context


def _searchresults_records(request_GET, limit=10):
    records = []

    def serialize_record(each):
        return {
            "id": each.id,
            "q": each.q,
            "original_q": each.original_q,
            "documents_found": each.documents_found,
            "search_time": each.search_time.total_seconds(),
            "search_times": each.search_times,
            "search_terms": each.search_terms,
            "keywords": each.keywords,
            "created": each.created,
        }

    qs = SearchResult.objects.all()
    q = request_GET.get("q")
    if q:
        qs = qs.filter(q__contains=q)

    for each in qs.order_by("-created")[:limit]:
        record = serialize_record(each)
        records.append(record)

    return records


geoip_looker_upper = GeoIP2()


@lru_cache()
def ip_to_city(ip_address):
    if ip_address == "127.0.0.1":
        return
    try:
        return geoip_looker_upper.city(ip_address)
    except AddressNotFoundError:
        return


@api_superuser_required
def blogcomments(request):
    if request.method == "POST":
        data = json.loads(request.body.decode("utf-8"))

        instance = BlogComment.objects.get(oid=data["oid"])
        form = EditBlogCommentForm(data, instance=instance)
        if form.is_valid():
            item = form.save()
            # Unsetting this will set it
            item.comment_rendered = ""
            item.rendered
            context = {
                "comment": item.comment,
                "rendered": item.rendered,
                "name": item.name,
                "email": item.email,
                "_clues": rate_blog_comment(item),
            }
            return _response(context, status=200)
        else:
            return _response({"errors": form.errors}, status=400)

    all_ids = set()

    all_parent_ids = set()
    for each in (
        BlogComment.objects.filter(parent__isnull=False).values("parent_id").distinct()
    ):
        all_parent_ids.add(each["parent_id"])

    @lru_cache()
    def get_blogitem_comment_add_dates(blogitem_id):
        qs = BlogComment.objects.filter(blogitem_id=blogitem_id, parent__isnull=True)
        return list(qs.order_by("-add_date").values_list("id", flat=True))

    def get_comment_page(blog_comment):
        root_comment = blog_comment
        while root_comment.parent_id:
            root_comment = root_comment.parent
        ids = get_blogitem_comment_add_dates(blog_comment.blogitem_id)
        per_page = settings.MAX_RECENT_COMMENTS
        for i in range(settings.MAX_BLOGCOMMENT_PAGES):
            sub_list = ids[i * per_page : (i + 1) * per_page]
            if root_comment.id in sub_list:
                return i + 1

        return 1

    def _serialize_comment(item, blogitem=None):
        all_ids.add(item.id)
        record = {
            "id": item.id,
            "oid": item.oid,
            "approved": item.approved,
            "comment": item.comment,
            "rendered": item.rendered,
            "add_date": item.add_date,
            "modify_date": item.modify_date,
            "age_seconds": int((timezone.now() - item.add_date).total_seconds()),
            "_bumped": item.add_date > item.modify_date,
            "name": item.name,
            "email": item.email,
            "user_agent": item.user_agent,
            "location": item.ip_address and ip_to_city(item.ip_address) or None,
            "_clues": not item.approved and rate_blog_comment(item) or None,
            "replies": [],
        }
        # XXX why would it NOT have a blogitem?!
        page = get_comment_page(item)
        if page > 1:
            blog_post_url = reverse("blog_post", args=[blogitem.oid, page])
        else:
            blog_post_url = reverse("blog_post", args=[blogitem.oid])
        record["_absolute_url"] = blog_post_url + "#{}".format(item.oid)
        if blogitem:
            record["blogitem"] = {
                "id": blogitem.id,
                "oid": blogitem.oid,
                "title": blogitem.title,
                "_absolute_url": reverse("blog_post", args=[blogitem.oid]),
            }

        if item.id in all_parent_ids:
            for reply in BlogComment.objects.filter(parent=item).order_by("add_date"):
                record["replies"].append(_serialize_comment(reply, blogitem=blogitem))
        record["max_add_date"] = max(
            [record["add_date"]] + [x["add_date"] for x in record["replies"]]
        )
        return record

    batch_size = settings.ADMINUI_COMMENTS_BATCH_SIZE
    base_qs = BlogComment.objects

    since = request.GET.get("since")
    if since == "null":
        since = None
    if since:
        base_qs = base_qs.filter(add_date__lt=since)

    if request.GET.get("unapproved") == "only":
        base_qs = base_qs.filter(approved=False)

    search = request.GET.get("search", "").lower().strip()
    blogitem_regex = re.compile(r"blogitem:([^\s]+)")
    if search and blogitem_regex.findall(search):
        blogitem_oid, = blogitem_regex.findall(search)
        search = blogitem_regex.sub("", search).strip()
        base_qs = base_qs.filter(blogitem=BlogItem.objects.get(oid=blogitem_oid))
    if search:
        base_qs = base_qs.filter(
            Q(comment__icontains=search) | Q(oid=search) | Q(blogitem__oid=search)
        )

    # Latest root comments...
    items = base_qs.filter(parent__isnull=True)
    items = items.order_by("-add_date")
    items = items.select_related("blogitem")
    context = {"comments": [], "count": base_qs.count()}
    oldest = timezone.now()
    # n, m = ((page - 1) * batch_size, page * batch_size)
    # iterator = items[n:m]
    for item in items.select_related("blogitem")[:batch_size]:
        if item.add_date < oldest:
            oldest = item.add_date
        context["comments"].append(_serialize_comment(item, blogitem=item.blogitem))

    comment_cache = {}
    for comment in (
        BlogComment.objects.all()
        .select_related("blogitem")
        .order_by("-add_date")[:1000]
    ):
        comment_cache[comment.id] = comment

    def get_parent(comment):
        if comment.parent_id:
            if comment.parent_id not in comment_cache:
                comment_cache[comment.parent_id] = comment.parent
            return comment_cache[comment.parent_id]

    # Latest not-root comments that haven't been included yet...
    new_replies = base_qs.filter(parent__isnull=False).exclude(id__in=all_ids)
    for comment in new_replies.order_by("-add_date")[:batch_size]:
        if comment.add_date < oldest:
            oldest = comment.add_date
        if comment.id in all_ids:
            continue
        while comment.parent_id:
            comment = get_parent(comment)
        context["comments"].append(
            _serialize_comment(comment, blogitem=comment.blogitem)
        )

    context["comments"].sort(key=lambda c: c["max_add_date"], reverse=True)
    context["oldest"] = oldest

    countries_map = {}

    def gather_all_countries(comments):
        for comment in comments:
            if comment.get("location"):
                country = comment["location"]["country_name"]
                if not country:
                    continue
                if country not in countries_map:
                    assert comment["location"]["country_code"], comment
                    countries_map[country] = {
                        "count": 0,
                        "name": country,
                        "country_code": comment["location"]["country_code"],
                    }
                countries_map[country]["count"] += 1
            if comment.get("replies"):
                gather_all_countries(comment["replies"])

    gather_all_countries(context["comments"])

    countries = sorted(countries_map.values(), key=lambda x: x["count"], reverse=True)
    context["countries"] = countries

    return _response(context)


@require_POST
@api_superuser_required
def blogcomments_batch(request, action):
    assert action in ("delete", "approve")
    data = json.loads(request.body.decode("utf-8"))
    data["comments"] = data.pop("oids")
    form = BlogCommentBatchForm(data)
    if form.is_valid():
        context = {"approved": [], "deleted": []}
        for comment in form.cleaned_data["comments"]:
            if action == "approve":
                # This if statement is to protect against possible
                # double submissions from the client.
                if not comment.approved:
                    actually_approve_comment(comment)
                    context["approved"].append(comment.oid)
            elif action == "delete":
                context["deleted"].append(comment.oid)
                comment.delete()
        return _response(context, status=200)
    else:
        print("ERRORS", form.errors)
        return _response({"errors": form.errors}, status=400)


def actually_approve_comment(blogcomment):
    blogcomment.approved = True
    blogcomment.save()

    if (
        blogcomment.parent
        and blogcomment.parent.email
        and valid_email(blogcomment.parent.email)
        and blogcomment.email != blogcomment.parent.email
    ):
        send_comment_reply_email.schedule(
            (blogcomment.id,), delay=settings.DELAY_SENDING_BLOGCOMMENT_REPLY_SECONDS
        )


@api_superuser_required
def blogitem_hits(request):
    context = {}
    limit = int(request.GET.get("limit", 50))
    today = request.GET.get("today", False)
    if today == "false":
        today = False
    _category_names = dict(
        (x["id"], x["name"]) for x in Category.objects.all().values("id", "name")
    )
    categories = defaultdict(list)
    qs = BlogItem.categories.through.objects.all().values("blogitem_id", "category_id")
    for each in qs:
        categories[each["blogitem_id"]].append(_category_names[each["category_id"]])
    context["categories"] = categories

    # XXX REFACTOR THIS TO USE THE ORM IF POSSIBLE
    if today:
        query = BlogItem.objects.raw(
            """
            WITH counts AS (
                SELECT
                    blogitem_id, count(blogitem_id) AS count
                    FROM plog_blogitemhit
                    WHERE add_date > NOW() - INTERVAL '1 day'
                    GROUP BY blogitem_id

            )
            SELECT
                b.id, b.oid, b.title, count AS hits, b.pub_date,
                EXTRACT(DAYS FROM (NOW() - b.pub_date))::INT AS age,
                count AS score
            FROM counts, plog_blogitem b
            WHERE
                blogitem_id = b.id AND (NOW() - b.pub_date) > INTERVAL '1 day'
            ORDER BY score desc
            LIMIT {limit}
        """.format(
                limit=limit
            )
        )
    else:
        query = BlogItem.objects.raw(
            """
            WITH counts AS (
                SELECT
                    blogitem_id, count(blogitem_id) AS count
                    FROM plog_blogitemhit
                    GROUP BY blogitem_id
            )
            SELECT
                b.id, b.oid, b.title, count AS hits, b.pub_date,
                EXTRACT(DAYS FROM (NOW() - b.pub_date))::INT AS age,
                count / EXTRACT(DAYS FROM (NOW() - b.pub_date)) AS score
            FROM counts, plog_blogitem b
            WHERE
                blogitem_id = b.id AND (NOW() - b.pub_date) > INTERVAL '1 day'
            ORDER BY score desc
            LIMIT {limit}
        """.format(
                limit=limit
            )
        )
    context["all_hits"] = []
    category_scores = defaultdict(list)
    for record in query:
        context["all_hits"].append(
            {
                "id": record.id,
                "oid": record.id,
                "title": record.title,
                "pub_date": record.pub_date,
                "hits": record.hits,
                "age": record.age,
                "score": record.score,
                "_absolute_url": "/plog/{}".format(record.oid),
            }
        )
        for cat in categories[record.id]:
            category_scores[cat].append(record.score)

    summed_category_scores = []
    for name, scores in category_scores.items():
        count = len(scores)
        summed_category_scores.append(
            {
                "name": name,
                "count": count,
                "sum": sum(scores),
                "avg": sum(scores) / count,
                "med": statistics.median(scores),
            }
        )
    context["summed_category_scores"] = summed_category_scores

    return _response(context)


@api_superuser_required
def blogitem_realtimehits(request):
    context = {"hits": [], "last_add_date": None}

    qs = BlogItemHit.objects.all().order_by("-add_date").select_related("blogitem")
    form = BlogitemRealtimeHitsForm(request.GET)
    if not form.is_valid():
        return _response({"errors": form.errors}, status=400)

    if form.cleaned_data["since"]:
        qs = qs.filter(add_date__gt=form.cleaned_data["since"])
    if form.cleaned_data["search"]:
        search = form.cleaned_data["search"]
        pub_date_regex = re.compile(
            r"(pub_date\s*([>=<]{1,2})\s*(\d{4})-(\d{2})-(\d{2}))"
        )
        for found in pub_date_regex.findall(search):
            whole, operator, yyyy, mm, dd = found
            date = datetime.datetime.combine(
                datetime.date(int(yyyy), int(mm), int(dd)), datetime.datetime.min.time()
            )
            pub_date = timezone.make_aware(date, timezone.now().tzinfo)
            orm_operator = {">=": "gte", ">": "gt", "<=": "lte", "<": "lt"}.get(
                operator, "exact"
            )
            qs = qs.filter(**{"blogitem__pub_date__" + orm_operator: pub_date})
            search = search.replace(whole, "").strip()
            if search.startswith(","):
                search = search[1:].strip()

        if search:
            qs = qs.filter(
                Q(blogitem__title__icontains=search)
                | Q(blogitem__oid__icontains=search)
            )

    today = timezone.now()
    for hit in qs[:30]:
        context["hits"].append(
            {
                "id": hit.id,
                "add_date": hit.add_date,
                "blogitem": {
                    "id": hit.blogitem.id,
                    "oid": hit.blogitem.oid,
                    "title": hit.blogitem.title,
                    "pub_date": hit.blogitem.pub_date,
                    "_is_published": hit.blogitem.pub_date < today,
                    "_absolute_url": "/plog/{}".format(hit.blogitem.oid),
                },
                # 'http_user_agent': hit.http_user_agent,
                # 'http_referer': hit.http_referer,
            }
        )

    if context["hits"]:
        context["last_add_date"] = max(
            x["add_date"] for x in context["hits"]
        ).isoformat()

    return _response(context)


@api_superuser_required
def hits(request, oid):
    blogitem = get_object_or_404(BlogItem, oid=oid)
    qs = BlogItemHit.objects.filter(blogitem=blogitem)
    today = timezone.now()

    context = {"hits": []}
    keys = (
        ("last_1_day", 1, "Last 1 day"),
        ("last_7_days", 7, "Last 7 days"),
        ("last_30_days", 30, "Last 30 days"),
        ("total", 0, "Ever"),
    )
    for key, days, label in keys:
        this_qs = qs.all()
        if days:
            since = today - datetime.timedelta(days=days)
            if since < blogitem.pub_date:
                continue
            this_qs = this_qs.filter(add_date__gte=since)
        count = this_qs.aggregate(count=Count("blogitem_id"))["count"]
        context["hits"].append({"key": key, "label": label, "value": count})

    return _response(context)


@api_superuser_required
def cdn_config(request):
    r = _get_cdn_config()
    context = {"data": r["data"]}
    return _response(context)


def _get_cdn_config():
    api = keycdn.Api(settings.KEYCDN_API_KEY)
    cache_key = "cdn_config:{}".format(settings.KEYCDN_ZONE_ID)
    r = cache.get(cache_key)
    if r is None:
        r = api.get("zones/{}.json".format(settings.KEYCDN_ZONE_ID))
        cache.set(cache_key, r, 60 * 5)
    return r


@require_POST
@api_superuser_required
def cdn_probe(request):
    url = request.POST["url"]
    if url.startswith("http://") or url.startswith("https://"):
        absolute_url = url
    elif "/" not in url:
        try:
            blogitem = BlogItem.objects.get(oid=url)
        except BlogItem.DoesNotExist:
            try:
                blogitem = BlogItem.objects.get(title__istartswith=url)
            except BlogItem.DoesNotExist:
                return _response({"error": "OID not found"}, status=400)
        absolute_url = "https://" + settings.KEYCDN_HOST
        absolute_url += reverse("blog_post", args=[blogitem.oid])
    else:
        return _response({"error": "Invalid search"}, status=400)

    context = {"absolute_url": absolute_url}
    r = requests.get(absolute_url)
    context["status_code"] = r.status_code
    if r.status_code == 200:
        context["x_cache"] = r.headers.get("x-cache")
        context["headers"] = dict(r.headers)
    return _response(context)


@require_POST
@api_superuser_required
def cdn_purge(request):
    urls = request.POST.getlist("urls")

    config = _get_cdn_config()
    # See https://www.keycdn.com/api#purge-zone-url
    cachebr = config["data"]["zone"]["cachebr"] == "enabled"
    all_urls = []
    for absolute_url in urls:
        url = settings.KEYCDN_HOST + urlparse(absolute_url).path
        all_urls.append(url)
        if cachebr:
            all_urls.append(url + "br")
    api = keycdn.Api(settings.KEYCDN_API_KEY)
    call = "zones/purgeurl/{}.json".format(settings.KEYCDN_ZONE_ID)
    params = {"urls": all_urls}
    r = api.delete(call, params)
    context = {"purge": {"result": r, "all_urls": all_urls}}
    return _response(context)
