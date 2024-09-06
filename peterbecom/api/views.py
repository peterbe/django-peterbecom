import datetime
import json
import os
import re
import statistics
import time
from collections import defaultdict
from functools import lru_cache, wraps
from urllib.parse import urlparse

import requests
from django import http
from django.conf import settings
from django.core.cache import cache
from django.db.models import Avg, Count, Max, Min, Q, Sum
from django.db.models.functions import Trunc
from django.db.utils import IntegrityError
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.timesince import timesince as django_timesince
from django.views.decorators.cache import cache_control, never_cache
from django.views.decorators.http import require_POST
from requests.exceptions import ConnectionError
from sorl.thumbnail import get_thumbnail

from peterbecom.base.cdn import (
    get_cdn_base_url,
    get_cdn_config,
    keycdn_zone_check,
)
from peterbecom.base.geo import ip_to_city
from peterbecom.base.models import (
    CDNPurgeURL,
    PostProcessing,
    SearchResult,
    UserProfile,
)
from peterbecom.base.utils import do_healthcheck, fake_ip_address
from peterbecom.base.xcache_analyzer import get_x_cache
from peterbecom.plog.models import (
    BlogComment,
    BlogFile,
    BlogItem,
    BlogItemDailyHits,
    BlogItemHit,
    Category,
    SpamCommentPattern,
)
from peterbecom.plog.popularity import score_to_popularity
from peterbecom.plog.utils import rate_blog_comment, valid_email  # move this some day

from .forms import (
    BlogCommentBatchForm,
    BlogFileUpload,
    BlogitemRealtimeHitsForm,
    CommentCountsIntervalForm,
    EditBlogCommentForm,
    EditBlogForm,
    PreviewBlogForm,
    SpamCommentPatternForm,
)
from .tasks import send_comment_reply_email


def timesince(*args, **kwargs):
    return django_timesince(*args, **kwargs).replace("\xa0", " ")


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
            "archived": item.archived,
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
        is_regex = re.compile(r"is:\s*(archived|future|published|unpublished)")
        for found in is_regex.findall(search):
            if found == "archived":
                qs = qs.filter(archived__isnull=False)
            elif found == "future":
                qs = qs.filter(pub_date__gt=timezone.now())
            elif found == "published":
                qs = qs.filter(pub_date__lt=timezone.now())
            elif found == "unpublished":
                qs = qs.filter(pub_date__gt=timezone.now())
            search = is_regex.sub("", search).strip()

        category_names = []
        cat_regex = re.compile(r"((cat|category):\"?\s*([\w\s]+))\"?")
        for found in cat_regex.findall(search):
            category_names.append(found[2])
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

    if request.method == "DELETE":
        item.delete()
        return _response({"deleted": True})

    if request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
        except json.decoder.JSONDecodeError:
            print(f"BODY: {request.body.decode("utf-8")!r}")
            return _response({"error": "Invalid JSON"}, status=400)

        if "toggle_archived" in data:
            if item.archived:
                item.archived = None
            else:
                item.archived = timezone.now()
            item.save()
            item.refresh_from_db()
        else:
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
            "_published": item.pub_date < timezone.now(),
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
            "archived": item.archived,
        }
    }
    return _response(context)


def categories(request):
    # Prepare all the names and IDs
    all_categories = {}
    for id, name in Category.objects.all().values_list("id", "name"):
        all_categories[id] = {"name": name, "count": 0, "id": id}

    # Gather each categories usage count
    qs = (
        BlogItem.categories.through.objects.all()
        .values("category_id")
        .annotate(count=Count("category_id"))
    )
    for count in qs:
        all_categories[count["category_id"]]["count"] = count["count"]

    seen = set()
    categories = []
    # Most recently created blogitem first
    qs = (
        BlogItem.categories.through.objects.all()
        .order_by("-blogitem__id")
        .values("category_id")
    )
    for bc in qs[:100]:
        id = bc["category_id"]
        if id in seen:
            continue
        categories.append(all_categories[id])
        seen.add(id)

    for id, category in all_categories.items():
        if id not in seen:
            categories.append(category)

    context = {"categories": categories}
    return _response(context)


class PreviewValidationError(Exception):
    """When something is wrong with the preview data."""


@api_superuser_required
@require_POST
def preview(request):
    post_data = json.loads(request.body.decode("utf-8"))
    post_data["pub_date"] = timezone.now()
    try:
        html = preview_by_data(post_data)
    except PreviewValidationError as exception:
        (form_errors,) = exception.args
        context = {"blogitem": {"errors": form_errors}}
        return _response(context, status=400)
    context = {"blogitem": {"html": html}}
    return _response(context)


def preview_by_data(data):
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
    post.title = "Doesn't matter"
    post.text = form.cleaned_data["text"]
    post.display_format = form.cleaned_data["display_format"]
    post.codesyntax = ""
    return post.rendered


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


def thumbnail(imagefile, geometry, **options):
    if not options.get("format"):
        # then let's try to do it by the file name
        filename = imagefile
        if hasattr(imagefile, "name"):
            # it's an ImageFile object
            filename = imagefile.name
        if filename.lower().endswith(".png"):
            options["format"] = "PNG"
        elif filename.lower().endswith(".gif"):
            pass
        else:
            options["format"] = "JPEG"
    try:
        return get_thumbnail(imagefile, geometry, **options)
    except IntegrityError:
        # The write is not transactional, and since this is most likely
        # used in a write-view, we might get conflicts trying to write and a
        # remember. Just try again a little bit later.
        time.sleep(1)
        return thumbnail(imagefile, geometry, **options)


@api_superuser_required
@never_cache
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
        (last,) = base_qs.filter(exception__isnull=True).order_by("-created")[:1]
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
            "_latest": None,
        }

    qs = PostProcessing.objects.all()
    qs = _filter_postprocessing_queryset(qs, request_GET)

    for each in qs.select_related("previous").order_by("-created")[:limit]:
        record = serialize_record(each)
        if each.previous:
            record["_previous"] = serialize_record(each.previous)
        if each.exception:
            # Search for a successful one that looks just like this
            sub_qs = PostProcessing.objects.filter(
                url=each.url,
                filepath=each.filepath,
                exception__isnull=True,
                created__gt=each.created,
            )
            for better in sub_qs.order_by("-created")[:1]:
                record["_latest"] = serialize_record(better)
                break
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

    if request_GET.get("exceptions"):
        qs = qs.filter(exception__isnull=False)
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
        (last,) = base_qs.order_by("-created")[:1]
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


@api_superuser_required
@never_cache
def blogcomments(request):
    if request.method == "POST":
        data = json.loads(request.body.decode("utf-8"))

        instance = BlogComment.objects.get(oid=data["oid"])
        form = EditBlogCommentForm(data, instance=instance)
        if form.is_valid():
            item = form.save()
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

    def make_commenter_hash_key(name, email):
        return "{}:{}".format(name, email)

    commenters = defaultdict(list)
    all_commenters_qs = BlogComment.objects.exclude(name="", email="")
    for name, email, blogitem_id in all_commenters_qs.values_list(
        "name", "email", "blogitem_id"
    ):
        commenters[make_commenter_hash_key(name, email)].append(blogitem_id)

    def get_commenter_count(name, email, blogitem_id):
        return commenters[make_commenter_hash_key(name, email)].count(blogitem_id)

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
        else:
            return None
        return 1

    def _serialize_comment(item, blogitem=None):
        all_ids.add(item.id)
        geo_lookup = item.geo_lookup
        if item.ip_address and not geo_lookup:
            if item.create_geo_lookup():
                item.refresh_from_db()
                geo_lookup = item.geo_lookup
        record = {
            "id": item.id,
            "oid": item.oid,
            "approved": item.approved,
            "auto_approved": item.auto_approved,
            "comment": item.comment,
            "rendered": item.rendered,
            "add_date": item.add_date,
            "modify_date": item.modify_date,
            "age_seconds": int((timezone.now() - item.add_date).total_seconds()),
            "_bumped": item.add_date > item.modify_date,
            "name": item.name,
            "email": item.email,
            "user_agent": item.user_agent,
            "location": geo_lookup,
            "_clues": not item.approved and rate_blog_comment(item) or None,
            "replies": [],
        }
        page = get_comment_page(item)
        record["page"] = page
        if page is not None and page > 1:
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

            if item.name or item.email:
                record["user_other_comments_count"] = get_commenter_count(
                    item.name, item.email, blogitem.id
                )

        if item.id in all_parent_ids:
            replies_qs = BlogComment.objects.filter(parent=item)
            for reply in replies_qs.order_by("add_date"):
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
    elif request.GET.get("autoapproved") == "only":
        base_qs = base_qs.filter(auto_approved=True)

    search = request.GET.get("search", "").lower().strip()
    blogitem_regex = re.compile(r"blogitem:([^\s]+)")
    if search and blogitem_regex.findall(search):
        (blogitem_oid,) = blogitem_regex.findall(search)
        not_blogitem = False
        if blogitem_oid.startswith("!"):
            not_blogitem = True
            blogitem_oid = blogitem_oid[1:]
        search = blogitem_regex.sub("", search).strip()
        search_blogitem = BlogItem.objects.get(oid=blogitem_oid)
        if not_blogitem:
            base_qs = base_qs.exclude(blogitem=search_blogitem)
        else:
            base_qs = base_qs.filter(blogitem=search_blogitem)
    if search:
        base_qs = base_qs.filter(
            Q(comment__icontains=search) | Q(oid=search) | Q(blogitem__oid=search)
        )

    # Hide old farts
    long_time_ago = timezone.now() - datetime.timedelta(days=30 * 12)
    base_qs = base_qs.exclude(add_date__lt=long_time_ago)

    # Latest root comments...
    items = base_qs.filter(parent__isnull=True)
    items = items.order_by("-add_date")
    items = items.select_related("blogitem")
    context = {"comments": [], "count": base_qs.count()}
    oldest = timezone.now()
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

    # countries_map = {}

    # def gather_all_countries(comments):
    #     for comment in comments:
    #         if comment.get("location"):
    #             country = comment["location"]["country_name"]
    #             if not country:
    #                 continue
    #             if country not in countries_map:
    #                 assert comment["location"]["country_code"], comment
    #                 countries_map[country] = {
    #                     "count": 0,
    #                     "name": country,
    #                     "country_code": comment["location"]["country_code"],
    #                 }
    #             countries_map[country]["count"] += 1
    #         if comment.get("replies"):
    #             gather_all_countries(comment["replies"])

    # gather_all_countries(context["comments"])

    # countries = sorted(countries_map.values(), key=lambda x: x["count"], reverse=True)
    # context["countries"] = countries

    return _response(context)


@api_superuser_required
def comment_auto_approved_records(request):
    context = {"records": _get_auto_approve_good_comments_records()}
    return _response(context)


def _get_auto_approve_good_comments_records():
    records = []
    for date, count in cache.get("auto-approve-good-comments", []):
        records.append({"date": date, "count": count, "human": timesince(date)})
    median_frequency_minutes = None
    next_run = None
    if len(records) > 3:
        distances = []
        previous = latest = records[0]
        for i, record in enumerate(records[1:]):
            distances.append(previous["date"] - record["date"])
            previous = record
        median_frequency = statistics.median(distances)
        median_frequency_minutes = int(median_frequency.total_seconds() / 60)
        next_run = latest["date"] + median_frequency
        next_run_minutes = (next_run - timezone.now()).total_seconds() / 60

    return {
        "records": records,
        "median_frequency_minutes": median_frequency_minutes,
        "next_run": next_run
        and {"date": next_run, "minutes": next_run_minutes}
        or None,
    }


@require_POST
@api_superuser_required
def blogcomments_batch(request, action):
    assert action in ("delete", "approve")
    data = json.loads(request.body.decode("utf-8"))
    data["comments"] = data.pop("oids")
    form = BlogCommentBatchForm(data)
    if form.is_valid():
        context = {"approved": [], "deleted": []}
        # Important to always approve the (potential) parents before the children.
        for comment in form.cleaned_data["comments"].order_by("add_date"):
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


def actually_approve_comment(blogcomment, auto_approved=False):
    blogcomment.approved = True
    blogcomment.auto_approved = auto_approved
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
def geocomments(request):
    comments = []
    qs = BlogComment.objects.filter(geo_lookup__isnull=False)
    qs = qs.select_related("blogitem")
    values = ("id", "geo_lookup", "name", "email", "blogitem__title", "blogitem__oid")
    for item in qs.values(*values).order_by("-add_date")[:100]:
        comments.append(
            {
                "id": item["id"],
                "location": item["geo_lookup"],
                "name": item["name"],
                "email": item["email"],
                "blogitem": {
                    "title": item["blogitem__title"],
                    "oid": item["blogitem__oid"],
                },
            }
        )

    return _response(
        {"comments": comments, "google_maps_api_key": settings.GOOGLE_MAPS_API_KEY}
    )


@api_superuser_required
def comment_counts(request):
    form = CommentCountsIntervalForm(data=request.GET, initial={"days": 28})

    if not form.is_valid():
        return _response(form.errors.get_json_data(), status=400)
    start = form.cleaned_data["start"]
    end = form.cleaned_data["end"]
    qs = BlogComment.objects.filter(
        add_date__gte=start - datetime.timedelta(days=1), add_date__lt=end
    )
    aggregates = (
        qs.annotate(day=Trunc("add_date", "day", tzinfo=start.tzinfo))
        .values("day")
        .annotate(count=Count("id"))
        .values("day", "count")
        .order_by("day")
    )
    dates = []
    for aggregate in aggregates:
        dates.append({"date": aggregate["day"].date(), "count": aggregate["count"]})

    return _response({"dates": dates})


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
                b.id, b.oid, b.title, b.popularity, count AS hits, b.pub_date,
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
                    blogitem_id, sum(total_hits) AS count
                    FROM plog_blogitemdailyhits
                    GROUP BY blogitem_id
            )
            SELECT
                b.id, b.oid, b.title, b.popularity, count AS hits, b.pub_date,
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
        # Convert Decimal to float
        record.score = float(record.score)
        context["all_hits"].append(
            {
                "id": record.id,
                "oid": record.id,
                "title": record.title,
                "pub_date": record.pub_date,
                "hits": record.hits,
                "age": record.age,
                "popularity": record.popularity or 0.0,
                "score": record.score,
                "log10_score": score_to_popularity(record.score),
                "_absolute_url": f"/plog/{record.oid}",
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
    daily_qs = BlogItemDailyHits.objects.filter(blogitem=blogitem)
    today = timezone.now()

    context = {"hits": []}
    keys = (
        ("last_1_day", 1, "Last 1 day"),
        ("last_7_days", 7, "Last 7 days"),
        ("last_30_days", 30, "Last 30 days"),
        ("total", 365, "Last year"),
    )
    last_1_day = 0
    for key, days, label in keys:
        if days == 1:
            since = today - datetime.timedelta(days=days)
            if since < blogitem.pub_date:
                continue
            count = qs.filter(add_date__gte=since).aggregate(
                count=Count("blogitem_id")
            )["count"]
            last_1_day = count
            context["hits"].append({"key": key, "label": label, "value": count})
        else:
            since = today - datetime.timedelta(days=days)
            start_of_date = since.replace(hour=0, minute=0, second=0, microsecond=0)
            count = (
                daily_qs.filter(date__gte=start_of_date.date()).aggregate(
                    count=Sum("total_hits")
                )["count"]
                or 0
            )
            context["hits"].append(
                {"key": key, "label": label, "value": count + last_1_day}
            )

    return _response(context)


@api_superuser_required
def cdn_config(request):
    context = {}
    if keycdn_zone_check():
        r = get_cdn_config()
        context["data"] = r["data"]
    else:
        context["error"] = "KeyCDN Zone Check currently failing"
    return _response(context)


@require_POST
@api_superuser_required
def cdn_probe(request):
    url = request.POST["url"].strip()
    blogitem = None

    base_url = "http"
    if request.is_secure():
        base_url += "s"
    base_url += "://" + request.get_host()

    if url.startswith("/"):  # rewrite to absolute URL
        url = base_url + url

    if url.startswith("http://") or url.startswith("https://"):
        absolute_url = url.split("#")[0]
        if (
            urlparse(absolute_url).netloc == request.get_host()
            and "/plog/" in absolute_url
            and urlparse(absolute_url).path not in ("/plog/", "/plog")
        ):
            oid = urlparse(absolute_url).path.split("/")[-1]
            try:
                blogitem = BlogItem.objects.get(oid=oid)
            except BlogItem.DoesNotExist:
                pass
    elif "/" not in url:
        try:
            blogitem = BlogItem.objects.get(oid=url)
        except BlogItem.DoesNotExist:
            try:
                blogitem = BlogItem.objects.get(title__istartswith=url)
            except BlogItem.DoesNotExist:
                return _response({"error": "OID not found"}, status=400)

        absolute_url = get_cdn_base_url()
        absolute_url += reverse("blog_post", args=[blogitem.oid])
    else:
        return _response({"error": "Invalid search"}, status=400)

    context = {"absolute_url": absolute_url}

    if blogitem and not re.findall(r"/p\d+$", absolute_url):
        comment_count = BlogComment.objects.filter(
            blogitem=blogitem, approved=True, parent__isnull=True
        ).count()
        pages = comment_count // settings.MAX_RECENT_COMMENTS
        other_pages = []
        for page in range(2, pages + 2):
            if page > settings.MAX_BLOGCOMMENT_PAGES:
                break
            url = reverse("blog_post", args=[blogitem.oid, page])
            other_pages.append(
                {
                    "url": base_url + url,
                }
            )

        if other_pages:
            context["other_pages"] = other_pages

    t0 = time.time()
    r = requests.get(absolute_url)
    t1 = time.time()
    context["http_1"] = {}
    context["http_1"]["took"] = t1 - t0
    context["http_1"]["status_code"] = r.status_code
    if r.status_code == 200:
        context["http_1"]["x_cache"] = r.headers.get("x-cache")
        context["http_1"]["headers"] = dict(r.headers)

    # Do a http2 GET too when requests3 or hyper has a new release
    # See https://github.com/Lukasa/hyper/issues/364
    context["http_2"] = {}
    return _response(context)


@require_POST
@api_superuser_required
def cdn_purge(request):
    context = {"deleted": []}
    urls_raw = request.POST.getlist("urls")
    urls = []
    for url in urls_raw:
        if "://" in url:
            url = urlparse(url).path
        urls.append(url)

    try:
        CDNPurgeURL.validate_urls(urls)
    except ValueError as exception:
        return http.HttpResponseBadRequest(str(exception))

    CDNPurgeURL.add(urls)
    context["purge"] = {"all_urls": urls, "results": [[u, "queued"] for u in urls]}
    return _response(context)


@api_superuser_required
def cdn_check(request):
    checked = keycdn_zone_check(refresh=True)
    return _response({"checked": checked})


@api_superuser_required
def cdn_purge_urls(request):
    qs = CDNPurgeURL.objects.filter(processed__isnull=True, cancelled__isnull=True)
    queued = []
    for item in qs:
        queued.append(
            {
                "id": item.id,
                "url": item.url,
                "attempts": item.attempts,
                "exception": item.exception,
                "attempted": item.attempted,
                "created": item.created,
            }
        )

    qs = CDNPurgeURL.objects.exclude(processed__isnull=True, cancelled__isnull=True)
    recent = []
    for item in qs.order_by("-created")[:50]:
        recent.append(
            {
                "id": item.id,
                "url": item.url,
                "attempts": item.attempts,
                "processed": item.processed,
                "cancelled": item.cancelled,
                "created": item.created,
            }
        )

    return _response({"queued": queued, "recent": recent})


def cdn_purge_urls_count(request):
    qs = CDNPurgeURL.objects.filter(processed__isnull=True, cancelled__isnull=True)
    return _response({"purge_urls": {"count": qs.count()}})


@api_superuser_required
def spam_comment_patterns(request, id=None):
    if request.method == "DELETE":
        assert id
        SpamCommentPattern.objects.get(id=id).delete()

    elif request.method == "POST":
        data = json.loads(request.body.decode("utf-8"))
        form = SpamCommentPatternForm(data)
        if form.is_valid():
            form.save()
        else:
            return _response({"errors": form.errors}, status=400)

    patterns = []
    qs = SpamCommentPattern.objects.all()
    for pattern in qs.order_by("add_date"):
        patterns.append(
            {
                "id": pattern.id,
                "add_date": pattern.add_date,
                "modify_date": pattern.modify_date,
                "pattern": pattern.pattern,
                "is_regex": pattern.is_regex,
                "is_url_pattern": pattern.is_url_pattern,
                "kills": pattern.kills,
            }
        )
    context = {"patterns": patterns}
    return _response(context)


@cache_control(max_age=60, public=True)
def lyrics_page_healthcheck(request):
    if request.get_host() == "localhost:8000":
        BASE_URL = "http://peterbecom.local"
    else:
        BASE_URL = "https://www.peterbe.com"
    URL = BASE_URL + "/plog/blogitem-040601-1"
    USER_AGENT = "peterbe/lyrics_page_healthcheck:bot"

    search_url = request.GET.get("url")

    def check():
        if search_url:
            t0 = time.time()
            result = check_url(search_url)
            t1 = time.time()
            yield (t1 - t0, search_url, result)
            return

        for page in range(1, settings.MAX_BLOGCOMMENT_PAGES + 1):
            if page == 1:
                url = URL
            else:
                url = URL + "/p{}".format(page)
            t0 = time.time()
            result = check_url(url)
            t1 = time.time()
            yield (t1 - t0, url, result)

    session = requests.Session()

    def catch_request_errors(f):
        @wraps(f)
        def inner(url):
            try:
                return f(url)
            except requests.exceptions.RequestException as exception:
                return (False, "{} on {}".format(exception, url))

        return inner

    @catch_request_errors
    def check_url(url):
        r = session.get(url, headers={"User-Agent": USER_AGENT}, timeout=3)
        if r.status_code != 200:
            return False, "Status code: {}".format(r.status_code)

        # The CDN origin's absolute shouldn't be in there
        count = r.text.count("www-origin.peterbe.com")
        if count:
            return False, "Origin domain in HTML ({} times)".format(count)

        count = r.text.count("<!-- /songsearch-autocomplete -->")
        if not count:
            return False, "The songsearch-autocomplete part isn't there!"
        if count > 1:
            return False, "Multiple songsearch-autocomplete there"

        react_scripts = re.findall(
            r"/songsearch-autocomplete/js/main.[a-f0-9]{8}.chunk.js", r.text
        )
        preact_scripts = re.findall(
            r"/songsearch-autocomplete-preact/bundle.[a-f0-9]{5}.js", r.text
        )
        if react_scripts:
            if len(react_scripts) > 1:
                return False, [">1 script files referenced!"] + react_scripts
        elif preact_scripts:
            if len(preact_scripts) != 1:
                return False, [">1 script files referenced!"] + preact_scripts
        else:
            return False, "No script files referenced!"

        # As of requests >=2.26 it sends `br` in the 'Accept-Encoding' by default.
        try:
            if r.headers["Content-Encoding"] != "br":
                return False, "No Brotli Content-Encoding"
        except KeyError:
            if "peterbecom.local" not in url:
                raise

        try:
            int(r.headers["Content-Length"])
        except KeyError:
            return False, "No Content-Length header. Probably no index.html.gz"

        if "peterbecom.local" not in url:
            r2 = session.get(
                url,
                headers={"Accept-encoding": "gzip", "User-Agent": USER_AGENT},
                timeout=3,
            )
            try:
                if r2.headers["content-encoding"] != "gzip":
                    # It works but it's not perfect.
                    return True, "Content-Encoding is not gzip!"
            except KeyError:
                return True, "No 'Content-Encoding' header"
            data = r2.text
            if data != r.text:
                return True, "Brotli content different from Gzip content"

        r3 = session.get(
            url, headers={"Accept-encoding": "", "User-Agent": USER_AGENT}, timeout=3
        )
        if r3.text != r.text:
            # This MIGHT fail because Nginx proxy caching not working locally.
            return True, "Plain content different from Gzip content ({})".format(url)

        # if "Stats from using github.com/peterbe/minimalcss" not in r.text:
        #     return False, "minimalcss not run on HTML"

        css_bit = (
            "License for minified and inlined CSS originally belongs to Semantic UI"
        )
        if r.text.count(css_bit) != 1:
            return (
                False,
                "Not exactly 1 ({}) CSS bits about inline css".format(
                    r.text.count(css_bit)
                ),
            )

        return True, None

    health = []
    for took, url, (works, errors) in check():
        if errors and not isinstance(errors, list):
            errors = [errors]
        if works and errors:
            state = "WARNING"
        elif works:
            errors = None
            state = "OK"
        else:
            state = "ERROR"
        health.append({"health": state, "url": url, "errors": errors, "took": took})
    context = {"health": health}
    return _response(context)


@require_POST
@api_superuser_required
def xcache_analyze(request):
    url = request.POST.get("url")
    assert "://" in url, "not an absolute URL"

    # To make it slighly more possible to test from locally
    url = url.replace("http://peterbecom.local", "https://www.peterbe.com")
    try:
        results = get_x_cache(url)
    except ConnectionError:
        # Not really a huge problem
        return http.HttpResponseServerError("ConnectionError")

    return _response({"xcache": results})


@never_cache
def whoami(request):
    context = {
        "is_authenticated": request.user.is_authenticated,
    }
    if request.user.is_authenticated:
        context["user"] = {
            "username": request.user.username,
            "email": request.user.email,
            "is_superuser": request.user.is_superuser,
            "csrfmiddlewaretoken": get_token(request),
        }
        for user_profile in UserProfile.objects.filter(user=request.user):
            if user_profile.claims.get("picture"):
                context["user"]["picture_url"] = user_profile.claims["picture"]
            break
    return _response(context)


@never_cache
def whereami(request):
    ip_addresses = request.headers.get("x-forwarded-for") or request.META.get(
        "REMOTE_ADDR"
    )
    # X-Forwarded-For might be a comma separated list of IP addresses
    # coming from the CDN. The first is the client.
    # https://www.keycdn.com/blog/x-forwarded-for-cdn
    ip_address = [x.strip() for x in ip_addresses.split(",") if x.strip()][0]
    if not ip_address:
        return _response({"error": "No remote IP address"}, status=412)
    context = {}
    if ip_address == "127.0.0.1" and request.get_host().endswith("peterbecom.local"):
        ip_address = fake_ip_address(str(time.time()))
        context["faked_ip_address"] = True
    context["ip_address"] = ip_address
    context["geo"] = ip_to_city(ip_address)
    return _response(context)


@never_cache
def healthcheck(request):
    do_healthcheck()
    return http.HttpResponse("OK\n")
