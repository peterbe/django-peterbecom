import datetime
import logging
import random
import re
from collections import defaultdict
from ipaddress import IPv4Address

from django import http
from django.conf import settings
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods, require_POST
from huey.contrib.djhuey import task

from peterbecom.awspa.models import AWSProduct
from peterbecom.base.templatetags.jinja_helpers import thumbnail
from peterbecom.base.utils import get_base_url

from . import utils
from .forms import CalendarDataForm
from .models import BlogComment, BlogItem, BlogItemHit, Category
from .spamprevention import contains_spam_patterns, contains_spam_url_patterns
from .tasks import send_new_comment_email
from .utils import get_blogcomment_slice, json_view, render_comment_text

logger = logging.getLogger("plog.views")


def fake_ip_address(seed):
    random.seed(seed)
    # https://codereview.stackexchange.com/a/200348
    return str(IPv4Address(random.getrandbits(32)))


class AWSPAError(Exception):
    """happens when we get a Product Links API error"""


ONE_HOUR = 60 * 60
ONE_DAY = ONE_HOUR * 24
ONE_WEEK = ONE_DAY * 7
ONE_MONTH = ONE_WEEK * 4
ONE_YEAR = ONE_WEEK * 52
THIS_YEAR = timezone.now().year


@cache_control(public=True, max_age=settings.DEBUG and ONE_HOUR or ONE_WEEK)
def blog_post(request, oid, page=None):
    if request.path.endswith("/ping"):
        # Sometimes this can happen when the URL parsing by Django
        # isn't working out.
        # E.g.
        # http://localhost:8000/plog/dont-forget-your-sets-in-python%0A/ping
        return blog_post_ping(request)
    # legacy fix
    if request.GET.get("comments") == "all":
        if "/all-comments" in request.path:
            return http.HttpResponseBadRequest("invalid URL")
        return redirect(request.path + "/all-comments", permanent=True)

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
            http_user_agent=user_agent,
            http_accept_language=request.headers.get("Accept-Language"),
            remote_addr=remote_addr,
            http_referer=http_referer,
            page=page,
        )
    return http.JsonResponse({"ok": True})


@task()
def increment_blogitem_hit(
    oid,
    http_user_agent=None,
    http_accept_language=None,
    remote_addr=None,
    http_referer=None,
    page=None,
):
    if http_referer and len(http_referer) > 450:
        http_referer = http_referer[: 450 - 3] + "..."
    try:
        blogitem_id = BlogItem.objects.values_list("id", flat=True).get(oid=oid)
        BlogItemHit.objects.create(
            # blogitem=BlogItem.objects.get(oid=oid),
            blogitem_id=blogitem_id,
            http_user_agent=http_user_agent,
            http_accept_language=http_accept_language,
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
            if oid == "add":
                return redirect(reverse("add_post"))
            raise http.Http404(oid)

    # If you try to view a blog post that is beyond one day in the
    # the future it should raise a 404 error.
    future = timezone.now() + datetime.timedelta(days=1)
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
    post._absolute_url = base_url + reverse("blog_post", args=(post.oid,))

    context = {"post": post, "screenshot_mode": screenshot_mode}
    if "/plog/blogitem-040601-1" not in request.path:
        try:
            context["previous_post"] = post.get_previous_by_pub_date()
        except BlogItem.DoesNotExist:
            context["previous_post"] = None
        try:
            context["next_post"] = post.get_next_by_pub_date(
                pub_date__lt=timezone.now()
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
        context["related_by_keyword"] = get_related_posts_by_keyword(post, limit=5)
        context["show_buttons"] = not screenshot_mode
    context["show_carbon_ad"] = not screenshot_mode
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

    response = render(request, "plog/post.html", context)
    response["x-server"] = "django"
    return response


@cache_control(public=True, max_age=7 * 24 * 60 * 60)
def all_blog_post_comments(request, oid):

    if request.path == "/plog/blogitem-040601-1/all-comments":
        raise http.Http404("No longer supported")

    post = get_object_or_404(BlogItem, oid=oid)
    comments = BlogComment.objects.filter(blogitem=post).order_by("add_date")
    comments = comments.filter(approved=True)

    all_comments = defaultdict(list)
    for comment in comments:
        all_comments[comment.parent_id].append(comment)
    data = {"post": post, "all_comments": all_comments}
    return render(request, "plog/_all_comments.html", data)


def get_related_posts_by_keyword(post, limit=5):
    if not post.proper_keywords:
        return BlogItem.objects.none()
    return (
        BlogItem.objects.filter(
            proper_keywords__overlap=post.proper_keywords, pub_date__lt=timezone.now()
        )
        .exclude(id=post.id)
        .order_by("-pub_date")[:limit]
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
    comment = request.POST.get("comment", u"").strip()
    name = request.POST.get("name", u"").strip()
    email = request.POST.get("email", u"").strip()
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
    post = get_object_or_404(BlogItem, oid=oid)
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

    for blog_comment in BlogComment.objects.filter(**search):
        break
    else:
        ip_address = request.headers.get("x-forwarded-for") or request.META.get(
            "REMOTE_ADDR"
        )
        print("IP_ADDRESS:", repr(ip_address))
        if ip_address == "127.0.0.1" and settings.FAKE_BLOG_COMMENT_IP_ADDRESS:
            ip_address = fake_ip_address(str(name) + str(email))
            print("FAKE IP_ADDRESS:", repr(ip_address))

        blog_comment = BlogComment.objects.create(
            oid=BlogComment.next_oid(),
            blogitem=post,
            parent=parent,
            approved=False,
            comment=comment,
            name=name,
            email=email,
            ip_address=ip_address,
            user_agent=request.headers.get("User-Agent"),
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

    response = http.JsonResponse(data)
    return response


@cache_control(public=True, max_age=60 * 60 * 24)
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
        BlogItem.objects.filter(pub_date__lt=now)
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


@cache_control(public=True, max_age=ONE_DAY)
def blog_post_awspa(request, oid, page=None):
    if page:
        return redirect("blog_post_awspa", oid)
    try:
        blogitem = BlogItem.objects.get(oid=oid)
    except BlogItem.DoesNotExist:
        try:
            blogitem = BlogItem.objects.get(oid__iexact=oid)
        except BlogItem.DoesNotExist:
            raise http.Http404()

    keywords = blogitem.get_all_keywords()
    if not keywords:
        # print("Blog post without any keywords", oid)
        # with open("/tmp/no-keywords-awsproducts.log", "a") as f:
        #     f.write("{}\n".format(oid))
        awsproducts = AWSProduct.objects.none()
    else:
        awsproducts = AWSProduct.objects.exclude(disabled=True).filter(
            keyword__in=keywords
        )

    instances = []
    seen = set()
    for awsproduct in awsproducts:

        # Disable any that don't have a MediumImage any more.
        if isinstance(awsproduct.payload, list):
            # Something must have gone wrong
            awsproduct.delete()
            continue
        if not awsproduct.payload.get("MediumImage"):
            awsproduct.disabled = True
            awsproduct.save()

        if awsproduct.asin not in seen:
            instances.append(awsproduct)
            seen.add(awsproduct.asin)

    if not instances:
        print("No matching AWSProducts!", keywords, "OID:", oid)
        with open("/tmp/no-matching-awsproducts.log", "a") as f:
            f.write("{}\n".format(oid))

    random.shuffle(instances)
    context = {"awsproducts": instances[:3]}
    return render(request, "plog/post-awspa.html", context)
