import datetime
import hashlib
import json
import logging
import os
import random
import re

# import zlib
from collections import defaultdict

# from io import BytesIO
from statistics import median
from urllib.parse import urlencode, urlparse

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
from peterbecom.awspa.search import search as awspa_search
from peterbecom.base.templatetags.jinja_helpers import thumbnail

# from peterbecom.bayes.guesser import default_guesser
# from peterbecom.bayes.models import BayesData, BlogCommentTraining

from . import utils
from .forms import BlogFileUpload, BlogForm, CalendarDataForm
from .models import (
    BlogComment,
    BlogFile,
    BlogItem,
    BlogItemHit,
    Category,
    HTMLRenderingError,
    OneTimeAuthKey,
)
from .search import BlogItemDoc
from .utils import (
    json_view,
    rate_blog_comment,
    render_comment_text,
    utc_now,
    valid_email,
    view_function_timer,
)

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
        context["related_by_text"] = get_related_posts_by_text(post, limit=5)
        context["show_buttons"] = not screenshot_mode
    context["show_carbon_ad"] = not screenshot_mode
    context["home_url"] = request.build_absolute_uri("/")
    context["page_title"] = post.title
    context["pub_date_years"] = THIS_YEAR - post.pub_date.year
    return render(request, "plog/post.html", context)


@cache_control(public=True, max_age=7 * 24 * 60 * 60)
@cache_page(ONE_WEEK, _blog_post_key_prefixer)
def all_blog_post_comments(request, oid):

    # temporary debugging
    if request.method == "GET":
        print(
            "all_blog_post_comments.MISS (%r, %r, %s)"
            % (
                request.path,
                request.META.get("QUERY_STRING"),
                timezone.now().isoformat(),
            )
        )

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


def get_related_posts_by_text(post, limit=5):
    search = BlogItemDoc.search()
    search.update_from_dict(
        {
            "query": {
                "more_like_this": {
                    "fields": ["title", "text"],
                    "like": [
                        {
                            "_index": settings.ES_BLOG_ITEM_INDEX,
                            "_type": "doc",
                            "_id": post.id,
                        }
                    ],
                    "min_term_freq": 2,
                    "min_doc_freq": 5,
                    "min_word_length": 3,
                    "max_query_terms": 25,
                }
            }
        }
    )
    search.update_from_dict({"query": {"range": {"pub_date": {"lt": "now"}}}})
    search = search[:limit]
    response = search.execute()
    ids = [int(x._id) for x in response]
    # print('Took {:.1f}ms to find {} related by text'.format(
    #     response.took,
    #     response.hits.total,
    # ))
    if not ids:
        return []
    objects = BlogItem.objects.filter(pub_date__lt=timezone.now(), id__in=ids)
    return sorted(objects, key=lambda x: ids.index(x.id))


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
    comment = request.POST["comment"].strip()
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
    ):
        return http.HttpResponseBadRequest("Looks too spammy")

    name = request.POST.get("name", u"").strip()
    email = request.POST.get("email", u"").strip()
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

        if request.user.is_authenticated:
            actually_approve_comment(blog_comment)
            assert blog_comment.approved
        elif post.oid != "blogitem-040601-1":
            # Let's not send an more admin emails for "Find songs by lyrics"
            tos = [x[1] for x in settings.ADMINS]
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


@require_POST
@login_required
def approve_delete_blog_post_comments(request, action):
    assert action in ("approve", "delete"), action
    blogcomments = []
    for id in request.POST["ids"].split(","):
        blogcomments.append(get_object_or_404(BlogComment, id=id))
    approved = []
    deleted = []
    for blogcomment in blogcomments:
        if action == "approve":
            actually_approve_comment(blogcomment)
            approved.append(blogcomment.id)
        elif action == "delete":
            deleted.append(blogcomment.id)
            blogcomment.delete()

    response = http.JsonResponse({"approved": approved, "delete": deleted})
    return response


@login_required
def approve_comment(request, oid, comment_oid):
    try:
        blogitem = BlogItem.objects.get(oid=oid)
    except BlogItem.DoesNotExist:
        return http.HttpResponse("BlogItem {!r} can't be found".format(oid), status=404)
    try:
        blogcomment = BlogComment.objects.get(oid=comment_oid)
        if blogcomment.approved:
            url = blogitem.get_absolute_url()
            if blogcomment.blogitem:
                url += "#%s" % blogcomment.oid
            return http.HttpResponse(
                """<html>Comment already approved<br>
                <a href="{}">{}</a>
                </html>
                """.format(
                    url, blogitem.title
                )
            )
    except BlogComment.DoesNotExist:
        return http.HttpResponse(
            "BlogComment {!r} can't be found".format(comment_oid), status=404
        )
    if blogcomment.blogitem != blogitem:
        raise http.Http404("bad rel")

    if request.method == "POST":
        if not request.user.is_superuser:
            return http.HttpResponseForbidden("Not superuser")
    else:
        forbidden = _check_auth_key(request, blogitem, blogcomment)
        if forbidden:
            return forbidden

    actually_approve_comment(blogcomment)

    if request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest":
        return http.HttpResponse("OK")
    else:
        url = blogitem.get_absolute_url()
        if blogcomment.blogitem:
            url += "#%s" % blogcomment.oid
        return http.HttpResponse(
            """<html>Comment approved<br>
            <a href="{}">{}</a>
            </html>
            """.format(
                url, blogitem.title
            )
        )


def _check_auth_key(request, blogitem, blogcomment):
    # Temporary thing. Delete this end of 2017.
    start_date = timezone.make_aware(datetime.datetime(2017, 9, 24))
    if blogcomment.add_date < start_date:
        return
    key = request.GET.get("key")
    if not key:
        return http.HttpResponseForbidden("No key")
    try:
        found = OneTimeAuthKey.objects.get(
            key=key, blogitem=blogitem, blogcomment=blogcomment, used__isnull=True
        )
        found.used = timezone.now()
        found.save()
    except OneTimeAuthKey.DoesNotExist:
        return http.HttpResponseForbidden("Key not found or already used")


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
    approve_url = reverse("approve_comment", args=[blogitem.oid, blogcomment.oid])
    approve_url += "?key={}".format(
        OneTimeAuthKey.objects.create(blogitem=blogitem, blogcomment=blogcomment).key
    )
    delete_url = reverse("delete_comment", args=[blogitem.oid, blogcomment.oid])
    delete_url += "?key={}".format(
        OneTimeAuthKey.objects.create(blogitem=blogitem, blogcomment=blogcomment).key
    )
    template = loader.get_template("plog/comment_body.txt")
    context = {
        "post": blogitem,
        "comment": blogcomment,
        "approve_url": approve_url,
        "delete_url": delete_url,
        "base_url": base_url,
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


@login_required
def delete_comment(request, oid, comment_oid):
    user = request.user
    assert user.is_staff or user.is_superuser
    try:
        blogitem = BlogItem.objects.get(oid=oid)
    except BlogItem.DoesNotExist:
        return http.HttpResponse("BlogItem {!r} can't be found".format(oid), status=404)
    try:
        blogcomment = BlogComment.objects.get(oid=comment_oid)
    except BlogComment.DoesNotExist:
        return http.HttpResponse(
            "BlogComment {!r} can't be found".format(comment_oid), status=404
        )
    if blogcomment.blogitem != blogitem:
        raise http.Http404("bad rel")

    if request.method == "POST":
        if not request.user.is_superuser:
            return http.HttpResponseForbidden("Not superuser")
    else:
        forbidden = _check_auth_key(request, blogitem, blogcomment)
        if forbidden:
            return forbidden

    blogcomment.delete()

    url = blogitem.get_absolute_url()
    return http.HttpResponse(
        """<html>Comment deleted<br>
        <a href="{}">{}</a>
        </html>
        """.format(
            url, blogitem.title
        )
    )


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


@cache_control(public=True, max_age=60 * 60 * 2)
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


def _new_comment_key_prefixer(request):
    if request.method != "GET":
        return None
    if request.user.is_authenticated:
        return None
    prefix = utils.make_prefix(request.GET)
    cache_key = "latest_comment_add_date"
    latest_date = cache.get(cache_key)
    if latest_date is None:
        latest, = BlogItem.objects.order_by("-modify_date").values("modify_date")[:1]
        latest_date = latest["modify_date"].strftime("%f")
        cache.set(cache_key, latest_date, 60 * 60)
    prefix += str(latest_date)
    return prefix


@cache_page(ONE_HOUR, _new_comment_key_prefixer)
def new_comments(request):
    context = {}
    comments = BlogComment.objects.all()
    if not request.user.is_superuser:
        comments = comments.filter(approved=True)
        context["comments"] = comments.order_by("-add_date").select_related("blogitem")[
            :50
        ]
    else:
        comments = comments.order_by("-add_date").select_related("blogitem")[:50]
        # bayes_data = BayesData.objects.get(topic="comments")
        # guesser = default_guesser
        # with BytesIO(zlib.decompress(bayes_data.pickle_data)) as f:
        #     guesser.load_handler(f)
        comments_list = []
        for comment in comments:
            # t = comment.name + " " + comment.comment
            # bayes_guess = dict(guesser.guess(t))
            # bayes_training = None
            # try:
            #     bayes_training = BlogCommentTraining.objects.get(
            #         comment=comment, bayes_data=bayes_data
            #     ).tag
            # except BlogCommentTraining.DoesNotExist:
            #     pass
            # comment.bayes_training = bayes_training
            # comment.bayes_guess = bayes_guess
            comment._clues = rate_blog_comment(comment)
            comments_list.append(comment)
        context["comments"] = comments_list
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
def plog_awspa(request, oid):
    blogitem = get_object_or_404(BlogItem, oid=oid)
    context = {"blogitem": blogitem}
    if request.method == "POST":
        keyword = request.POST.get("keyword")
        if keyword:
            # Load more!
            url = reverse("plog_awspa", args=(blogitem.oid,))
            try:
                new = load_more_awsproducts(
                    keyword, request.POST.get("searchindex", "All")
                )
                params = {"focus": keyword}
                if new:
                    params["new"] = [x.title for x in new]
            except AWSPAError as exception:
                error = exception.args[0]
                params = {"error": json.dumps(error)}
            url += "?" + urlencode(params, True)

            keywords = blogitem.get_all_keywords()
            if keyword.lower() not in keywords:
                blogitem.proper_keywords.append(keyword)
                blogitem.save()
            return redirect(url)

        asin = request.POST.get("asin")
        awsproduct = AWSProduct.objects.get(asin=asin)
        awsproduct.disabled = not awsproduct.disabled
        awsproduct.save()

        return http.HttpResponse("OK")

    all_keywords = blogitem.get_all_keywords()

    possible_products = {}
    for keyword in all_keywords:
        possible_products[keyword] = AWSProduct.objects.filter(
            keyword__iexact=keyword
        ).order_by("disabled", "modify_date")
    context["possible_products"] = possible_products

    context["all_keywords"] = all_keywords
    context["page_title"] = blogitem.title
    return render(request, "plog/awspa.html", context)


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
    context["all_hits"] = query

    category_scores = defaultdict(list)
    for item in query:
        for cat in categories[item.id]:
            category_scores[cat].append(item.score)

    summed_category_scores = []
    for name, scores in category_scores.items():
        count = len(scores)
        summed_category_scores.append(
            {
                "name": name,
                "count": count,
                "sum": sum(scores),
                "avg": sum(scores) / count,
                "med": median(scores),
            }
        )
    context["summed_category_scores"] = summed_category_scores
    context["page_title"] = "Hits"
    context["today"] = today
    return render(request, "plog/plog_hits.html", context)


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


@cache_page(ONE_DAY)
@view_function_timer("inner")
def blog_post_awspa(request, oid):
    try:
        blogitem = BlogItem.objects.get(oid=oid)
    except BlogItem.DoesNotExist:
        try:
            blogitem = BlogItem.objects.get(oid__iexact=oid)
        except BlogItem.DoesNotExist:
            raise http.Http404()

    seen = request.GET.getlist("seen")

    keywords = blogitem.get_all_keywords()
    if not keywords:
        print("Blog post without any keywords", oid)
        return http.HttpResponse("")

    awsproducts = AWSProduct.objects.exclude(disabled=True).filter(keyword__in=keywords)
    if seen and awsproducts.count() > 3:
        awsproducts = awsproducts.exclude(asin__in=seen)

    if not awsproducts.exists():
        print("No matching AWSProducts", keywords, "Seen:", seen)
        return http.HttpResponse("")

    # Disable any that don't have a MediumImage any more.
    for awsproduct in awsproducts:
        if isinstance(awsproduct.payload, list):
            # Something must have gone wrong
            awsproduct.delete()
            continue
        if not awsproduct.payload.get("MediumImage"):
            awsproduct.disabled = True
            awsproduct.save()

    instances = []
    seen = set()
    for awsproduct in awsproducts:
        if awsproduct.asin not in seen:
            instances.append(awsproduct)
            seen.add(awsproduct.asin)
    random.shuffle(instances)
    context = {"awsproducts": instances[:3]}
    return render(request, "plog/post-awspa.html", context)
