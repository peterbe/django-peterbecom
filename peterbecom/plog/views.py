import datetime
import hashlib
import logging
import os
import random
import re

from collections import defaultdict

from urllib.parse import urlparse

from django import http
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.sites.models import Site
from django.contrib.sites.requests import RequestSite
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.template import loader
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods, require_POST
from fancy_cache import cache_page
from huey.contrib.djhuey import task

from peterbecom.awspa.models import AWSProduct

from peterbecom.base.templatetags.jinja_helpers import thumbnail

from . import utils
from .forms import BlogFileUpload, BlogForm, CalendarDataForm
from .models import (
    BlogComment,
    BlogFile,
    BlogItem,
    BlogItemHit,
    Category,
    HTMLRenderingError,
)
from .spamprevention import contains_spam_url_patterns
from .utils import json_view, render_comment_text, utc_now, valid_email

logger = logging.getLogger("plog.views")


class AWSPAError(Exception):
    """happens when we get a Product Links API error"""


ONE_HOUR = 60 * 60
ONE_DAY = ONE_HOUR * 24
ONE_WEEK = ONE_DAY * 7
ONE_MONTH = ONE_WEEK * 4
ONE_YEAR = ONE_WEEK * 52
THIS_YEAR = timezone.now().year


def _blog_post_key_prefixer(request):
    prefix = getattr(request, "_prefix", None)
    if prefix is not None:
        return prefix
    # print("PREFIXED?", getattr(request, '_prefixed', None))
    if request.method != "GET":
        return None
    if request.user.is_authenticated:
        return None
    prefix = utils.make_prefix(request.GET)

    # all_comments = False
    if request.path.endswith("/all-comments"):
        oid = request.path.split("/")[-2]
        # all_comments = True
    elif request.path.endswith("/"):
        oid = request.path.split("/")[-2]
    else:
        oid = request.path.split("/")[-1]

    try:
        cache_key = "latest_comment_add_date:%s" % (
            hashlib.md5(oid.encode("utf-8")).hexdigest()
        )
    except UnicodeEncodeError:
        # If the 'oid' can't be converted to ascii, then it's not likely
        # to be a valid 'oid'.
        return None
    latest_date = cache.get(cache_key)
    if latest_date is None:
        try:
            blogitem = BlogItem.objects.filter(oid=oid).values("pk", "modify_date")[0]
        except IndexError:
            # don't bother, something's really wrong
            return None
        latest_date = blogitem["modify_date"]
        blogitem_pk = blogitem["pk"]
        for c in (
            BlogComment.objects.filter(
                blogitem=blogitem_pk, add_date__gt=latest_date, approved=True
            )
            .values("add_date")
            .order_by("-add_date")[:1]
        ):
            latest_date = c["add_date"]
        latest_date = latest_date.strftime("%f")
        cache.set(cache_key, latest_date, ONE_MONTH)
    prefix += str(latest_date)

    # This is a HACK!
    # This prefixer function gets called, first for the request,
    # then for the response. The answer is not going to be any different.
    request._prefix = prefix
    return prefix


@cache_control(public=True, max_age=settings.DEBUG and ONE_HOUR or ONE_WEEK)
@cache_page(settings.DEBUG and ONE_HOUR or ONE_WEEK, _blog_post_key_prefixer)
def blog_post(request, oid):
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

    return _render_blog_post(request, oid)


@require_http_methods(["PUT"])
@csrf_exempt
def blog_post_ping(request, oid):
    if not utils.is_bot(
        ua=request.META.get("HTTP_USER_AGENT", ""), ip=request.META.get("REMOTE_ADDR")
    ):
        http_referer = request.GET.get("referrer", request.META.get("HTTP_REFERER"))
        if http_referer:
            current_url = request.build_absolute_uri().split("/ping")[0]
            if current_url == http_referer:
                http_referer = None
        increment_blogitem_hit(
            oid,
            http_user_agent=request.META.get("HTTP_USER_AGENT"),
            http_accept_language=request.META.get("HTTP_ACCEPT_LANGUAGE"),
            remote_addr=request.META.get("REMOTE_ADDR"),
            http_referer=http_referer,
        )
    return http.JsonResponse({"ok": True})


@task()
def increment_blogitem_hit(
    oid,
    http_user_agent=None,
    http_accept_language=None,
    remote_addr=None,
    http_referer=None,
):
    if http_referer and len(http_referer) > 450:
        http_referer = http_referer[: 450 - 3] + "..."
    try:
        BlogItemHit.objects.create(
            blogitem=BlogItem.objects.get(oid=oid),
            http_user_agent=http_user_agent,
            http_accept_language=http_accept_language,
            http_referer=http_referer,
            remote_addr=remote_addr,
        )
    except BlogItem.DoesNotExist:
        print("Can't find BlogItem with oid {!r}".format(oid))


def blog_screenshot(request, oid):
    response = _render_blog_post(request, oid, screenshot_mode=True)
    return response


def _render_blog_post(request, oid, screenshot_mode=False):
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

    # Reasons for not being here
    if request.method == "HEAD":
        return http.HttpResponse("")
    elif request.method == "GET" and (
        request.GET.get("replypath") or request.GET.get("show-comments")
    ):
        return http.HttpResponsePermanentRedirect(request.path)

    # attach a field called `_absolute_url` which depends on the request
    base_url = "https://" if request.is_secure() else "http://"
    base_url += RequestSite(request).domain
    post._absolute_url = base_url + reverse("blog_post", args=(post.oid,))

    context = {"post": post, "screenshot_mode": screenshot_mode}
    if request.path != "/plog/blogitem-040601-1":
        try:
            context["previous_post"] = post.get_previous_by_pub_date()
        except BlogItem.DoesNotExist:
            context["previous_post"] = None
        try:
            context["next_post"] = post.get_next_by_pub_date(pub_date__lt=utc_now())
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

    comments = (
        BlogComment.objects.filter(blogitem=post, approved=True)
        .order_by("add_date")
        .only(
            "oid",
            "blogitem_id",
            "parent_id",
            "approved",
            "comment_rendered",
            "add_date",
            "name",
        )
    )
    comments_truncated = False
    count_comments = post.count_comments()
    if request.GET.get("comments") != "all":
        slice_m, slice_n = (
            max(0, count_comments - settings.MAX_RECENT_COMMENTS),
            count_comments,
        )
        if count_comments > settings.MAX_RECENT_COMMENTS:
            comments_truncated = settings.MAX_RECENT_COMMENTS
        comments = comments = comments[slice_m:slice_n]

    all_comments = defaultdict(list)
    for comment in comments:
        all_comments[comment.parent_id].append(comment)

    # print(all_comments.keys())

    context["comments_truncated"] = comments_truncated
    context["count_comments"] = count_comments
    context["all_comments"] = all_comments
    if request.path != "/plog/blogitem-040601-1":
        context["related_by_keyword"] = get_related_posts_by_keyword(post, limit=5)
        # context["related_by_text"] = get_related_posts_by_text(post, limit=5)
        context["show_buttons"] = not screenshot_mode
    context["show_carbon_ad"] = not screenshot_mode
    context["home_url"] = request.build_absolute_uri("/")
    context["page_title"] = post.title
    context["pub_date_years"] = THIS_YEAR - post.pub_date.year
    return render(request, "plog/post.html", context)


@cache_control(public=True, max_age=7 * 24 * 60 * 60)
@cache_page(ONE_WEEK, _blog_post_key_prefixer)
def all_blog_post_comments(request, oid):

    if request.path == "/plog/blogitem-040601-1/all-comments":
        raise http.Http404("No longer supported")

    post = get_object_or_404(BlogItem, oid=oid)
    comments = BlogComment.objects.filter(blogitem=post).order_by("add_date")
    if not request.user.is_staff:
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
@json_view
def prepare_json(request):
    data = {"csrf_token": request.META["CSRF_COOKIE"]}
    return http.JsonResponse(data)


@require_POST
@json_view
def preview_json(request):
    comment = request.POST.get("comment", u"").strip()
    name = request.POST.get("name", u"").strip()
    email = request.POST.get("email", u"").strip()
    if not comment:
        return {}

    html = render_comment_text(comment.strip())
    comment = {
        "oid": "preview-oid",
        "name": name,
        "email": email,
        "rendered": html,
        "add_date": utc_now(),
    }
    html = render_to_string("plog/comment.html", {"comment": comment, "preview": True})
    return {"html": html}


# Not using @json_view so I can use response.set_cookie first
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
        ("whatsapp" in comment_lower or "://" in comment)
        and ("@gmail.com" in comment_lower or "@yahoo.com" in comment_lower)
        and re.findall(r"\+\d+", comment)
    ) or (
        ("@gmail.com" in comment_lower or "@yahoo.com" in comment_lower)
        and (
            "spell" in comment or "healing" in comment or "call doctor" in comment_lower
        )
    ) or (
        contains_spam_url_patterns(comment)
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
        blog_comment = BlogComment.objects.create(
            oid=BlogComment.next_oid(),
            blogitem=post,
            parent=parent,
            approved=False,
            comment=comment,
            name=name,
            email=email,
            ip_address=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT"),
        )

        if post.oid != "blogitem-040601-1":
            # Let's not send an more admin emails for "Find songs by lyrics"
            tos = [x[1] for x in settings.MANAGERS]
            from_ = ["%s <%s>" % x for x in settings.MANAGERS][0]
            body = _get_comment_body(post, blog_comment)
            send_mail("Peterbe.com: New comment on '%s'" % post.title, body, from_, tos)

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


def actually_approve_comment(blogcomment):
    blogcomment.approved = True
    blogcomment.save()

    if (
        blogcomment.parent
        and blogcomment.parent.email
        and valid_email(blogcomment.parent.email)
        and blogcomment.email != blogcomment.parent.email
    ):
        parent = blogcomment.parent
        tos = [parent.email]
        from_ = "Peterbe.com <mail@peterbe.com>"
        body = _get_comment_reply_body(blogcomment.blogitem, blogcomment, parent)
        subject = "Peterbe.com: Reply to your comment"
        send_mail(subject, body, from_, tos)


def _get_comment_body(blogitem, blogcomment):
    base_url = "https://%s" % Site.objects.get_current().domain
    if "peterbecom.local" in base_url:
        base_url = "http://localhost:4000"
    admin_url = base_url.replace("www.", "admin.")
    template = loader.get_template("plog/comment_body.txt")
    context = {
        "post": blogitem,
        "comment": blogcomment,
        "base_url": base_url,
        "admin_url": admin_url,
    }
    return template.render(context).strip()


def _get_comment_reply_body(blogitem, blogcomment, parent):
    base_url = "https://%s" % Site.objects.get_current().domain
    template = loader.get_template("plog/comment_reply_body.txt")
    context = {
        "post": blogitem,
        "comment": blogcomment,
        "parent": parent,
        "base_url": base_url,
    }
    return template.render(context).strip()


def _plog_index_key_prefixer(request):
    if request.method != "GET":
        return None
    if request.user.is_authenticated:
        return None
    prefix = utils.make_prefix(request.GET)
    cache_key = "latest_post_modify_date"
    latest_date = cache.get(cache_key)
    if latest_date is None:
        latest, = BlogItem.objects.order_by("-modify_date").values("modify_date")[:1]
        latest_date = latest["modify_date"].strftime("%f")
        cache.set(cache_key, latest_date, ONE_DAY)
    prefix += str(latest_date)
    return prefix


@cache_control(public=True, max_age=60 * 60 * 24)
@cache_page(ONE_DAY, _plog_index_key_prefixer)
def plog_index(request):
    groups = defaultdict(list)
    now = utc_now()
    group_dates = []

    _categories = dict((x.pk, x.name) for x in Category.objects.all())
    blogitem_categories = defaultdict(list)
    for cat_item in BlogItem.categories.through.objects.all():
        blogitem_categories[cat_item.blogitem_id].append(
            _categories[cat_item.category_id]
        )
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

    data = {"groups": groups, "group_dates": group_dates, "page_title": "Blog archive"}
    return render(request, "plog/index.html", data)


@cache_control(public=True, max_age=60 * 60)
@cache_page(ONE_HOUR)
def new_comments(request):
    context = {}
    comments = BlogComment.objects.filter(approved=True).exclude(
        blogitem__oid="blogitem-040601-1"
    )
    context["comments"] = comments.order_by("-add_date").select_related("blogitem")[:40]
    context["page_title"] = "Latest new blog comments"
    return render(request, "plog/new-comments.html", context)


@login_required
@transaction.atomic
def add_post(request):
    context = {}
    user = request.user
    assert user.is_staff or user.is_superuser
    if request.method == "POST":
        form = BlogForm(data=request.POST)
        if form.is_valid():
            assert isinstance(form.cleaned_data["proper_keywords"], list)
            blogitem = BlogItem.objects.create(
                oid=form.cleaned_data["oid"],
                title=form.cleaned_data["title"],
                text=form.cleaned_data["text"],
                summary=form.cleaned_data["summary"],
                display_format=form.cleaned_data["display_format"],
                codesyntax=form.cleaned_data["codesyntax"],
                url=form.cleaned_data["url"],
                pub_date=form.cleaned_data["pub_date"],
                proper_keywords=form.cleaned_data["proper_keywords"],
            )
            for category in form.cleaned_data["categories"]:
                blogitem.categories.add(category)
            blogitem.save()

            url = reverse("edit_post", args=[blogitem.oid])
            return redirect(url)
    else:
        initial = {
            "pub_date": utc_now() + datetime.timedelta(seconds=60 * 60),
            "display_format": "markdown",
        }
        form = BlogForm(initial=initial)
    context["form"] = form
    context["page_title"] = "Add post"
    context["blogitem"] = None
    context["awsproducts"] = AWSProduct.objects.none()
    return render(request, "plog/edit.html", context)


@login_required
@transaction.atomic
def edit_post(request, oid):
    blogitem = get_object_or_404(BlogItem, oid=oid)
    data = {}
    user = request.user
    assert user.is_staff or user.is_superuser
    if request.method == "POST":
        form = BlogForm(instance=blogitem, data=request.POST)
        if form.is_valid():
            blogitem.oid = form.cleaned_data["oid"]
            blogitem.title = form.cleaned_data["title"]
            blogitem.text = form.cleaned_data["text"]
            blogitem.text_rendered = ""
            blogitem.summary = form.cleaned_data["summary"]
            blogitem.display_format = form.cleaned_data["display_format"]
            blogitem.codesyntax = form.cleaned_data["codesyntax"]
            blogitem.pub_date = form.cleaned_data["pub_date"]
            assert isinstance(form.cleaned_data["proper_keywords"], list)
            blogitem.proper_keywords = form.cleaned_data["proper_keywords"]
            blogitem.categories.clear()
            for category in form.cleaned_data["categories"]:
                blogitem.categories.add(category)
            blogitem.save()
            assert blogitem._render(refresh=True)

            url = reverse("edit_post", args=[blogitem.oid])
            return redirect(url)

    else:
        form = BlogForm(instance=blogitem)
    data["form"] = form
    data["page_title"] = "Edit post"
    data["blogitem"] = blogitem
    data["INBOUND_EMAIL_ADDRESS"] = settings.INBOUND_EMAIL_ADDRESS
    data["awsproducts"] = AWSProduct.objects.exclude(disabled=True).filter(
        keyword__in=blogitem.get_all_keywords()
    )
    return render(request, "plog/edit.html", data)


@login_required
@transaction.atomic
def plog_open_graph_image(request, oid):
    blogitem = get_object_or_404(BlogItem, oid=oid)
    context = {"blogitem": blogitem}
    options = []

    images_used = re.findall(r'<a href="(.*?)"', blogitem.text)
    images_used = [
        x
        for x in images_used
        if x.lower().endswith(".png") or x.lower().endswith(".jpg")
    ]
    images_used.extend(re.findall(r'<img src="(.*?)"', blogitem.text))
    images_used_paths = [urlparse(x).path for x in images_used]
    # print("IMAGES USED")
    # print(images_used)
    # print("IMAGES_USED_PATHS")
    # print(images_used_paths)
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
        src = request.POST.get("src")
        if not src or src not in [x["src"] for x in options]:
            return http.HttpResponseBadRequest("No src")
        if blogitem.open_graph_image and blogitem.open_graph_image == src:
            blogitem.open_graph_image = None
        else:
            blogitem.open_graph_image = src
        blogitem.save()
        url = reverse("edit_post", args=[blogitem.oid])
        return redirect(url)

    context["options"] = options
    context["page_title"] = blogitem.title
    return render(request, "plog/open-graph-image.html", context)


@csrf_exempt
@login_required
@require_POST
def preview_post(request, return_html_string=False):
    post_data = request.POST.dict()
    post_data["categories"] = request.POST.getlist("categories[]")
    try:
        html_string = preview_by_data(post_data, request)
        return http.HttpResponse(html_string)
    except HTMLRenderingError as exception:
        return http.JsonResponse({"error": str(exception)}, status=400)
    except PreviewValidationError as form:
        return http.HttpResponse(str(form.errors))


class PreviewValidationError(Exception):
    """When something is wrong with the preview data."""


def preview_by_data(data, request):
    from django.template import Context
    from django.template.loader import get_template

    post_data = dict()
    for key, value in data.items():
        if value:
            post_data[key] = value
    post_data["oid"] = "doesntmatter"
    post_data["keywords"] = []
    form = BlogForm(data=post_data)
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


@login_required
@transaction.atomic
def add_file(request):
    data = {}
    user = request.user
    assert user.is_staff or user.is_superuser
    if request.method == "POST":
        form = BlogFileUpload(request.POST, request.FILES)
        if form.is_valid():
            instance = form.save()
            url = reverse("edit_post", args=[instance.blogitem.oid])
            return redirect(url)
    else:
        initial = {}
        if request.GET.get("oid"):
            blogitem = get_object_or_404(BlogItem, oid=request.GET.get("oid"))
            initial["blogitem"] = blogitem
        form = BlogFileUpload(initial=initial)
    data["form"] = form
    return render(request, "plog/add_file.html", data)


@login_required
def post_thumbnails(request, oid):
    blogitem = get_object_or_404(BlogItem, oid=oid)
    images = _post_thumbnails(blogitem)
    return http.JsonResponse({"images": images})


def _post_thumbnails(blogitem):
    blogfiles = BlogFile.objects.filter(blogitem=blogitem).order_by("add_date")

    images = []

    for blogfile in blogfiles:
        if not os.path.isfile(blogfile.file.path):
            continue
        full_im = thumbnail(blogfile.file, "1000x1000", upscale=False, quality=100)
        full_url = full_im.url
        delete_url = reverse("delete_post_thumbnail", args=(blogfile.pk,))
        image = {
            "full_url": full_url,
            "full_size": full_im.size,
            "delete_url": delete_url,
        }
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


@login_required
@require_POST
def delete_post_thumbnail(request, pk):
    blogfile = get_object_or_404(BlogFile, pk=pk)
    blogfile.delete()
    return http.JsonResponse({"ok": True})


@cache_page(ONE_DAY)
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
    if not request.user.is_authenticated:
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
def blog_post_awspa(request, oid):
    try:
        blogitem = BlogItem.objects.get(oid=oid)
    except BlogItem.DoesNotExist:
        try:
            blogitem = BlogItem.objects.get(oid__iexact=oid)
        except BlogItem.DoesNotExist:
            raise http.Http404()

    keywords = blogitem.get_all_keywords()
    if not keywords:
        print("Blog post without any keywords", oid)
        with open("/tmp/no-keywords-awsproducts.log", "a") as f:
            f.write("{}\n".format(oid))
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
