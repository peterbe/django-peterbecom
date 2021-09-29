import datetime
import hashlib
import time
from collections import defaultdict

from django import http
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from peterbecom.base.utils import fake_ip_address
from peterbecom.plog.models import BlogComment, BlogItem, Category
from peterbecom.plog.spamprevention import (
    contains_spam_patterns,
    contains_spam_url_patterns,
    is_trash_commenter,
)
from peterbecom.plog.tasks import send_new_comment_email
from peterbecom.plog.utils import render_comment_text
from peterbecom.publicapi.forms import SubmitForm


def blogitems(request):
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
        item["comments"] = approved_comments_count.get(item["pk"], 0)
        item["id"] = item.pop("pk")
        groups[group].append(item)
        tup = (group, item["pub_date"].strftime("%B, %Y"))
        if tup not in group_dates:
            group_dates.append(tup)

    groups_list = []
    for key in groups:
        groups_list.append(
            {
                "date": key,
                "posts": groups[key],
            }
        )

    return http.JsonResponse({"groups": groups_list})


def blogpost(request, oid):
    try:
        blogitem = BlogItem.objects.get(oid__iexact=oid)
    except BlogItem.DoesNotExist:
        return http.HttpResponseNotFound(oid)

    future = timezone.now() + datetime.timedelta(days=10)
    if blogitem.pub_date > future:
        return http.HttpResponseNotFound("not published yet")
    if blogitem.archived:
        return http.HttpResponseNotFound("blog post archived")

    post = {
        "oid": blogitem.oid,
        "title": blogitem.title,
        "body": blogitem.text_rendered,
        "pub_date": blogitem.pub_date,
        "open_graph_image": blogitem.open_graph_image,
        "url": blogitem.url,
        "summary": blogitem.summary,
        "categories": [x.name for x in blogitem.categories.all()],
        "disallow_comments": blogitem.disallow_comments,
        "hide_comments": blogitem.hide_comments,
    }

    def serialize_related(post_objects):
        return [{"oid": x["oid"], "title": x["title"]} for x in post_objects]

    if blogitem.oid != "blogitem-040601-1":
        try:
            previous = blogitem.get_previous_by_pub_date(archived__isnull=True)
            # post["previous_post"] = {"oid": previous.oid, "title": previous.title}
        except BlogItem.DoesNotExist:
            previous = None

        try:
            next = blogitem.get_next_by_pub_date(
                pub_date__lt=timezone.now(),
                archived__isnull=True,
            )
            # post["next_post"] = {"oid": next.oid, "title": next.title}
        except BlogItem.DoesNotExist:
            next = None

        exclude_related = []
        if previous:
            post["previous_post"] = {"oid": previous.oid, "title": previous.title}
            exclude_related.append(previous.id)
        if next:
            post["next_post"] = {"oid": next.oid, "title": next.title}
            exclude_related.append(next.id)

        related_by_categories = list(
            get_related_posts_by_categories(
                blogitem, limit=5, exclude_ids=exclude_related
            ).values("id", "oid", "title")
        )
        exclude_related.extend([x["id"] for x in related_by_categories])
        post["related_by_categories"] = serialize_related(related_by_categories)

        related_by_keyword = list(
            get_related_posts_by_keyword(
                blogitem, limit=5, exclude_ids=exclude_related
            ).values("id", "oid", "title")
        )
        post["related_by_keyword"] = serialize_related(related_by_keyword)

    try:
        page = int(request.GET.get("page") or 1)
        if page <= 0:
            raise ValueError()
    except ValueError:
        return http.HttpResponseBadRequest("invalid page")

    if page > settings.MAX_BLOGCOMMENT_PAGES:
        return http.HttpResponseNotFound("gone too far")

    blogcomments = BlogComment.objects.filter(blogitem=blogitem, approved=True)
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

    comments = {}
    comments["truncated"] = comments_truncated
    comments["count"] = count_comments
    comments["tree"] = traverse_and_serialize_comments(all_comments)

    if page < settings.MAX_BLOGCOMMENT_PAGES:
        # But is there even a next page?!
        if page * settings.MAX_RECENT_COMMENTS < root_comments_count:
            comments["paginate_uri_next"] = f"/plog/{blogitem.oid}/p{page + 1}"
    if page > 1:
        if page == 2:
            comments["paginate_uri_previous"] = f"/plog/{blogitem.oid}"
        else:
            comments["paginate_uri_previous"] = f"/plog/{blogitem.oid}/p{page - 1}"

    return http.JsonResponse({"post": post, "comments": comments})


def traverse_and_serialize_comments(all_comments, comment=None, depth=None):
    tree = []
    if not comment:
        iterator = all_comments[None]
    else:
        iterator = all_comments[comment.id]
    depth = depth or 0
    for comment in iterator:
        serialized = serialize_comment(comment)
        serialized["depth"] = depth
        replies = traverse_and_serialize_comments(
            all_comments, comment=comment, depth=depth + 1
        )
        if replies:
            serialized["replies"] = replies
        tree.append(serialized)

    return tree


def serialize_comment(blogcomment):
    return {
        "id": blogcomment.id,
        "oid": blogcomment.oid,
        "add_date": blogcomment.add_date,
        "name": blogcomment.name or None,
        "comment": blogcomment.comment_rendered,
        "approved": bool(blogcomment.approved),
    }


def get_blogcomment_slice(count_comments, page):
    slice_m, slice_n = (
        max(0, count_comments - settings.MAX_RECENT_COMMENTS),
        count_comments,
    )
    slice_m -= (page - 1) * settings.MAX_RECENT_COMMENTS
    slice_m = max(0, slice_m)
    slice_n -= (page - 1) * settings.MAX_RECENT_COMMENTS

    return (slice_m, slice_n)


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


@ensure_csrf_cookie
def prepare_comment(request):
    token = request.META["CSRF_COOKIE"]
    return http.JsonResponse({"csrfmiddlewaretoken": token})


@require_POST
def preview_comment(request):
    comment = (request.POST.get("comment") or "").strip()
    if not comment:
        return http.HttpResponseBadRequest("empty comment")
    if len(comment) > 10_000:
        return http.HttpResponseBadRequest("too big")

    rendered = render_comment_text(comment)
    return http.JsonResponse({"comment": rendered})


@require_POST
def submit_comment(request):
    form = SubmitForm(request.POST)
    if not form.is_valid():
        return http.HttpResponseBadRequest(form.errors.as_json())

    from pprint import pprint

    pprint(form.cleaned_data)

    blogitem = form.cleaned_data["oid"]
    name = form.cleaned_data["name"]
    email = form.cleaned_data["email"]
    comment = form.cleaned_data["comment"]
    parent = form.cleaned_data["parent"]

    if contains_spam_url_patterns(comment) or contains_spam_patterns(comment):
        return http.HttpResponseBadRequest("Looks too spammy")

    ip_address = request.headers.get("x-forwarded-for") or request.META.get(
        "REMOTE_ADDR"
    )
    if ip_address == "127.0.0.1" and settings.FAKE_BLOG_COMMENT_IP_ADDRESS:
        ip_address = fake_ip_address(f"{name}{email}")

    user_agent = request.headers.get("User-Agent")

    if is_trash_commenter(
        name=name, email=email, ip_address=ip_address, user_agent=user_agent
    ):
        return http.JsonResponse({"trash": True}, status=400)

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
            blogitem=blogitem,
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
            print(f"WARNING! {exception!r} create_geo_lookup failed")

        if blogitem.oid != "blogitem-040601-1":
            transaction.on_commit(lambda: send_new_comment_email(blog_comment.id))

    # Generate a non-cryptographic hash that the user can user to edit their
    # comment after they posted it.
    blog_comment_hash = hashlib.md5(
        f"{blog_comment.oid}{time.time()}".encode("utf-8")
    ).hexdigest()
    cache_key = f"blog_comment_hash:{blog_comment_hash}"
    hash_expiration_seconds = 60 * 5
    cache.set(cache_key, blogitem.oid, hash_expiration_seconds)

    return http.JsonResponse(
        {
            "hash": blog_comment_hash,
            "hash_expiration_seconds": hash_expiration_seconds,
            "comment": blog_comment.comment_rendered,
        }
    )
