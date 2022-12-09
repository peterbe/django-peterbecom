import datetime
import logging
import re
from collections import defaultdict
from urllib.parse import urlparse

from django import http
from django.conf import settings
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.cache import add_never_cache_headers, patch_cache_control
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods, require_POST
from huey.contrib.djhuey import task

from peterbecom.base.templatetags.jinja_helpers import thumbnail
from peterbecom.base.utils import fake_ip_address, get_base_url

from . import utils
from .forms import CalendarDataForm
from .models import BlogComment, BlogItem, BlogItemHit, Category
from .spamprevention import (
    contains_spam_patterns,
    contains_spam_url_patterns,
    is_trash_commenter,
)
from .tasks import send_new_comment_email
from .utils import get_blogcomment_slice, json_view, render_comment_text

logger = logging.getLogger("plog.views")


ONE_HOUR = 60 * 60
ONE_DAY = ONE_HOUR * 24
ONE_WEEK = ONE_DAY * 7
ONE_MONTH = ONE_WEEK * 4
ONE_YEAR = ONE_WEEK * 52
THIS_YEAR = timezone.now().year


def blog_post(request, oid, page=None):
    if request.path.endswith("/ping"):
        # Sometimes this can happen when the URL parsing by Django
        # isn't working out.
        # E.g.
        # http://localhost:8000/plog/dont-forget-your-sets-in-python%0A/ping
        return blog_post_ping(request)

    # legacy stuff
    if request.GET.get("comments") == "all":
        return redirect(request.path, permanent=False)

    return _render_blog_post(request, oid, page=page)


@require_http_methods(["PUT"])
@csrf_exempt
def blog_post_ping(request, oid, page=None):
    user_agent = request.headers.get("User-Agent", "")
    remote_addr = request.META.get("REMOTE_ADDR")
    if not utils.is_bot(ua=user_agent, ip=remote_addr):
        http_referer = request.GET.get("referrer", request.headers.get("Referer"))
        if http_referer:
            current_url = request.build_absolute_uri().split("/ping")[0]
            if current_url == http_referer:
                http_referer = None
        increment_blogitem_hit(
            oid,
            remote_addr=remote_addr,
            http_referer=http_referer,
            page=page,
        )
    return http.JsonResponse({"ok": True})


@task()
def increment_blogitem_hit(
    oid,
    remote_addr=None,
    http_referer=None,
    page=None,
):
    if http_referer and len(http_referer) > 450:
        http_referer = http_referer[: 450 - 3] + "..."
    try:
        blogitem_id = BlogItem.objects.values_list("id", flat=True).get(oid=oid)
        BlogItemHit.objects.create(
            blogitem_id=blogitem_id,
            http_referer=http_referer,
            remote_addr=remote_addr,
            page=page,
        )
    except BlogItem.DoesNotExist:
        print("Can't find BlogItem with oid {!r}".format(oid))


def blog_screenshot(request, oid):
    response = _render_blog_post(request, oid, screenshot_mode=True)
    return response


def _render_blog_post(request, oid, page=None, screenshot_mode=False):
    if oid.endswith("/"):
        oid = oid[:-1]
    try:
        post = BlogItem.objects.get(oid=oid)
    except BlogItem.DoesNotExist:
        try:
            post = BlogItem.objects.get(oid__iexact=oid)
        except BlogItem.DoesNotExist:
            raise http.Http404(oid)

    if post.archived:
        return http.HttpResponseNotFound("blog post archived")

    # If you try to view a blog post that is beyond 10 days in the
    # the future it should raise a 404 error.
    future = timezone.now() + datetime.timedelta(days=10)
    if post.pub_date > future:
        raise http.Http404("not published yet")

    if page is None:
        page = 1
    else:
        page = int(page)
        if page == 1:
            return redirect("blog_post", oid)

    if page > settings.MAX_BLOGCOMMENT_PAGES:
        raise http.Http404("Gone too far")

    # Reasons for not being here
    if request.method == "HEAD":
        return http.HttpResponse("")
    elif request.method == "GET" and (
        request.GET.get("replypath") or request.GET.get("show-comments")
    ):
        return http.HttpResponsePermanentRedirect(request.path)

    # attach a field called `_absolute_url` which depends on the request
    base_url = get_base_url(request)

    # There was a time when my nginx was misconfigured an a bunch of URLs
    # accidentally got the wrong base URL. So there are lots of these indexed
    # by bots such as `https://api.minimalcss.app/plog/foo-bar`.
    # It can't technically happen any more but the existing links needs to be
    # fixed.
    if base_url == "https://api.minimalcss.app":
        return redirect(f"https://www.peterbe.com{request.path}", permanent=True)

    post._absolute_url = base_url + reverse("blog_post", args=(post.oid,))

    context = {"post": post, "screenshot_mode": screenshot_mode}
    if "/plog/blogitem-040601-1" not in request.path:
        try:
            context["previous_post"] = post.get_previous_by_pub_date(
                archived__isnull=True
            )
        except BlogItem.DoesNotExist:
            context["previous_post"] = None
        try:
            context["next_post"] = post.get_next_by_pub_date(
                pub_date__lt=timezone.now(),
                archived__isnull=True,
            )
        except BlogItem.DoesNotExist:
            context["next_post"] = None

    if post.screenshot_image:
        context["screenshot_image"] = thumbnail(
            post.screenshot_image, "1280x1000", quality=90
        ).url
        if context["screenshot_image"].startswith("//"):
            # facebook is not going to like that
            context["screenshot_image"] = "https:" + context["screenshot_image"]
    else:
        context["screenshot_image"] = None

    # Cheat a little and make the open graph image absolute if need be.
    if post.open_graph_image and "://" not in post.open_graph_image:
        post.open_graph_image = request.build_absolute_uri(post.open_graph_image)

    blogcomments = BlogComment.objects.filter(blogitem=post, approved=True)

    only = (
        "oid",
        "blogitem_id",
        "parent_id",
        "approved",
        "comment_rendered",
        "add_date",
        "name",
    )
    root_comments = (
        blogcomments.filter(parent__isnull=True).order_by("add_date").only(*only)
    )

    replies = blogcomments.filter(parent__isnull=False).order_by("add_date").only(*only)

    count_comments = blogcomments.count()

    root_comments_count = root_comments.count()

    if page > 1:
        if (page - 1) * settings.MAX_RECENT_COMMENTS > root_comments_count:
            raise http.Http404("Gone too far")

    slice_m, slice_n = get_blogcomment_slice(root_comments_count, page)
    root_comments = root_comments[slice_m:slice_n]

    comments_truncated = False
    if root_comments_count > settings.MAX_RECENT_COMMENTS:
        comments_truncated = settings.MAX_RECENT_COMMENTS

    all_comments = defaultdict(list)
    for comment in root_comments:
        all_comments[comment.parent_id].append(comment)

    for comment in replies:
        all_comments[comment.parent_id].append(comment)

    context["comments_truncated"] = comments_truncated
    context["count_comments"] = count_comments
    context["all_comments"] = all_comments
    if "/plog/blogitem-040601-1" not in request.path:
        exclude_related = []
        if context["previous_post"]:
            exclude_related.append(context["previous_post"].pk)
        if context["next_post"]:
            exclude_related.append(context["next_post"].pk)
        context["related_by_categories"] = get_related_posts_by_categories(
            post, limit=5, exclude_ids=exclude_related
        )
        exclude_related.extend(
            [x for x in context["related_by_categories"].values_list("id", flat=True)]
        )
        context["related_by_keyword"] = get_related_posts_by_keyword(
            post, limit=5, exclude_ids=exclude_related
        )
        context["show_buttons"] = not screenshot_mode
    context["show_carbon_ad"] = not screenshot_mode
    # context["show_carbon_ad"] = 0
    # context["show_carbon_native_ad"] = context["show_carbon_ad"]
    # Disabled as of Aug 2019 because the $$$ profit was too small and not
    # worth the web perf "drag" that it costs.
    context["show_carbon_native_ad"] = False
    context["home_url"] = request.build_absolute_uri("/")
    context["page_title"] = post.title
    context["pub_date_years"] = THIS_YEAR - post.pub_date.year
    context["page"] = page
    if page < settings.MAX_BLOGCOMMENT_PAGES:
        # But is there even a next page?!
        if page * settings.MAX_RECENT_COMMENTS < root_comments_count:
            context["paginate_uri_next"] = reverse(
                "blog_post", args=(post.oid, page + 1)
            )

    if page > 1:
        context["paginate_uri_previous"] = reverse(
            "blog_post", args=(post.oid, page - 1)
        )

    # The `post.open_graph_image` is a string. It looks something like this:
    # '/cache/1e/a7/1ea7b1a42e9161.png' and it would get rendered
    # into the template like this:
    #    <meta property="og:image" content="/cache/1e/a7/1ea7b1a42e9161.png">
    # But post-processing will make this an absolute URL. And that might
    # not pick up the smarts that `get_base_url(request)` can do so
    # turn this into a control template context variable.
    absolute_open_graph_image = None
    if post.open_graph_image:
        absolute_open_graph_image = base_url + urlparse(post.open_graph_image).path
    context["absolute_open_graph_image"] = absolute_open_graph_image

    context["not_published_yet"] = post.pub_date > timezone.now()

    response = render(request, "plog/post.html", context)
    response["x-server"] = "django"
    # If it hasn't been published yet, don't cache-control it.
    if context["not_published_yet"]:
        add_never_cache_headers(response)
    else:
        if settings.DEBUG:
            max_age = ONE_HOUR
        else:
            age_days = (timezone.now() - post.pub_date).days
            if age_days < 10:
                # Fresh and new, don't cache too long in case it needs to be edited
                max_age = ONE_DAY
            elif age_days < 100:
                max_age = ONE_WEEK
            else:
                # Default is a looong max-age because old blog posts are
                # likely to be veeery old.
                max_age = ONE_MONTH
        patch_cache_control(response, public=True, max_age=max_age)

    return response


# legacy stuff
def all_blog_post_comments(request, oid):
    return redirect(f"/plog/{oid}", permanent=True)


def get_related_posts_by_keyword(post, limit=5, exclude_ids=None):
    if not post.proper_keywords:
        return BlogItem.objects.none()
    return (
        BlogItem.objects.filter(
            proper_keywords__overlap=post.proper_keywords,
            pub_date__lt=timezone.now(),
            archived__isnull=True,
        )
        .exclude(id=post.id)
        .exclude(id__in=exclude_ids or [])
        .order_by("-popularity")[:limit]
    )


def get_related_posts_by_categories(post, limit=5, exclude_ids=None):
    if not post.categories.all().exists():
        return BlogItem.objects.none()
    return (
        BlogItem.objects.filter(
            categories__in=post.categories.all(),
            pub_date__lt=timezone.now(),
            archived__isnull=True,
        )
        .distinct()
        .exclude(id=post.id)
        .exclude(id__in=exclude_ids or [])
        .order_by("-popularity")[:limit]
    )


def _render_comment(comment):
    return render_to_string("plog/comment.html", {"comment": comment})


@ensure_csrf_cookie
def prepare_json(request):
    data = {"csrf_token": request.META["CSRF_COOKIE"]}
    return http.JsonResponse(data)


@ensure_csrf_cookie
@require_POST
def preview_json(request):
    comment = request.POST.get("comment", "").strip()
    name = request.POST.get("name", "").strip()
    email = request.POST.get("email", "").strip()
    if not comment:
        return http.JsonResponse({})

    html = render_comment_text(comment.strip())
    comment = {
        "oid": "preview-oid",
        "name": name,
        "email": email,
        "rendered": html,
        "add_date": timezone.now(),
    }
    html = render_to_string("plog/comment.html", {"comment": comment, "preview": True})
    return http.JsonResponse({"html": html})


@require_POST
@transaction.atomic
def submit_json(request, oid):
    post = get_object_or_404(BlogItem, oid=oid, archived__isnull=True)
    if post.disallow_comments:
        return http.HttpResponseBadRequest("No comments please")
    comment = request.POST.get("comment", "").strip()
    if not comment:
        return http.HttpResponseBadRequest("Missing comment")

    # I'm desperate so I'll put in some easy-peasy spam checks before I get around
    # to building a proper classifier.
    comment_lower = comment.lower()
    if (
        (
            ("whatsapp" in comment_lower or "://" in comment)
            and ("@gmail.com" in comment_lower or "@yahoo.com" in comment_lower)
            and re.findall(r"\+\d+", comment)
        )
        or (
            ("@gmail.com" in comment_lower or "@yahoo.com" in comment_lower)
            and (
                "spell" in comment
                or "healing" in comment
                or "call doctor" in comment_lower
            )
        )
        or contains_spam_url_patterns(comment)
        or contains_spam_patterns(comment)
    ):
        return http.HttpResponseBadRequest("Looks too spammy")

    name = request.POST.get("name", "").strip()
    email = request.POST.get("email", "").strip()

    parent = request.POST.get("parent")
    if parent:
        parent = get_object_or_404(BlogComment, oid=parent)
    else:
        parent = None  # in case it was u''

    search = {"comment": comment}
    if name:
        search["name"] = name
    if email:
        search["email"] = email
    if parent:
        search["parent"] = parent

    ip_address = request.headers.get("x-forwarded-for") or request.META.get(
        "REMOTE_ADDR"
    )
    if ip_address == "127.0.0.1" and settings.FAKE_BLOG_COMMENT_IP_ADDRESS:
        ip_address = fake_ip_address(str(name) + str(email))

    user_agent = request.headers.get("User-Agent")

    if is_trash_commenter(
        name=name, email=email, ip_address=ip_address, user_agent=user_agent
    ):
        return http.JsonResponse({"trash": True}, status=400)

    for blog_comment in BlogComment.objects.filter(**search):
        break
    else:
        blog_comment = BlogComment.objects.create(
            oid=BlogComment.next_oid(),
            blogitem=post,
            parent=parent,
            approved=False,
            comment=comment,
            name=name,
            email=email,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        try:
            blog_comment.create_geo_lookup()
        except Exception as exception:
            if settings.DEBUG:
                raise
            print("WARNING! {!r} create_geo_lookup failed".format(exception))

        if post.oid != "blogitem-040601-1":
            transaction.on_commit(lambda: send_new_comment_email(blog_comment.id))

    html = render_to_string(
        "plog/comment.html", {"comment": blog_comment, "preview": True}
    )
    _comments = BlogComment.objects.filter(approved=True, blogitem=post)
    comment_count = _comments.count() + 1
    data = {
        "html": html,
        "parent": parent and parent.oid or None,
        "comment_count": comment_count,
    }

    return http.JsonResponse(data)


@cache_control(public=True, max_age=60 * 60 * 24 * 2)
def plog_index(request):
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
        groups[group].append(item)
        tup = (group, item["pub_date"].strftime("%B, %Y"))
        if tup not in group_dates:
            group_dates.append(tup)

    data = {
        "groups": groups,
        "group_dates": group_dates,
        "page_title": "Blog archive",
        "approved_comments_count": approved_comments_count,
    }
    return render(request, "plog/index.html", data)


@cache_control(public=True, max_age=60 * 60)
def new_comments(request):
    context = {}
    comments = BlogComment.objects.filter(approved=True).exclude(
        blogitem__oid="blogitem-040601-1"
    )
    context["comments"] = comments.order_by("-add_date").select_related("blogitem")[:40]
    context["page_title"] = "Latest new blog comments"
    return render(request, "plog/new-comments.html", context)


@cache_control(public=True, max_age=60 * 60 * 24)
def calendar(request):
    context = {"page_title": "Archive calendar"}
    return render(request, "plog/calendar.html", context)


@json_view
def calendar_data(request):
    form = CalendarDataForm(request.GET)
    if not form.is_valid():
        return http.HttpResponseBadRequest(form.errors)
    start = form.cleaned_data["start"]
    end = form.cleaned_data["end"]
    end = min(end, timezone.now())
    if end < start:
        return []

    qs = BlogItem.objects.filter(pub_date__gte=start, pub_date__lt=end)
    items = []
    for each in qs:
        item = {
            "title": each.title,
            "start": each.pub_date,
            "url": reverse("blog_post", args=[each.oid]),
            "className": "post",
        }
        items.append(item)

    return items


def plog_hits(request):
    raise NotImplementedError("Moved to adminui")


def plog_hits_data(request):
    hits = {}

    def get_count(start, end):
        return BlogItemHit.objects.filter(add_date__gte=start, add_date__lt=end).count()

    now = timezone.now()

    hits["last_hour"] = get_count(now - datetime.timedelta(hours=1), now)
    now = now.replace(hour=0, minute=0, second=0)
    hits["today"] = get_count(now - datetime.timedelta(days=1), now)
    hits["yesterday"] = get_count(
        now - datetime.timedelta(days=2), now - datetime.timedelta(days=1)
    )
    hits["last_week"] = get_count(
        now - datetime.timedelta(days=1 + 7), now - datetime.timedelta(days=7)
    )
    hits["last_month"] = get_count(
        now - datetime.timedelta(days=1 + 30), now - datetime.timedelta(days=30)
    )

    return http.JsonResponse({"hits": hits})
