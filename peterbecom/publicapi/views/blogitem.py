import datetime
import math
from collections import defaultdict

from django import http
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from peterbecom.plog.models import (
    BlogComment,
    BlogItem,
    count_approved_comments,
    count_approved_root_comments,
)


def blogitem(request, oid):
    try:
        page = int(request.GET.get("page") or 1)
        if page <= 0:
            raise ValueError()
    except ValueError:
        return http.HttpResponseBadRequest("invalid page")

    if page > settings.MAX_BLOGCOMMENT_PAGES:
        return http.HttpResponseNotFound("gone too far")

    cache_key = f"publicapi_blogitem_{oid}:{page}"
    cached = cache.get(cache_key)
    if cached:
        return http.JsonResponse(cached)

    try:
        blogitem = BlogItem.objects.get(oid=oid)
    except BlogItem.DoesNotExist:
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

    def serialize_related(post_object):
        if isinstance(post_object, dict):
            return {
                "oid": post_object["oid"],
                "title": post_object["title"],
                "pub_date": post_object["pub_date"],
                "categories": post_object.get("categories", []),
            }
        return {
            "oid": post_object.oid,
            "title": post_object.title,
            "pub_date": post_object.pub_date,
            "categories": [x.name for x in post_object.categories.all()],
        }

    def serialize_related_objects(post_objects):
        return [serialize_related(x) for x in post_objects]

    post["previous_post"] = post["next_post"] = None

    if blogitem.oid != "blogitem-040601-1":
        base_qs = BlogItem.objects.filter(archived__isnull=True).values(
            "id", "oid", "title", "pub_date"
        )
        for previous in (
            base_qs.filter(pub_date__lt=blogitem.pub_date)
            .order_by("-pub_date")
            .values("id", "oid", "title", "pub_date")[:1]
        ):
            previous["categories"] = list(
                BlogItem.categories.through.objects.filter(
                    blogitem__id=previous["id"]
                ).values_list("category__name", flat=True)
            )
            break
        else:
            previous = None

        for next in (
            base_qs.filter(pub_date__lt=timezone.now(), pub_date__gt=blogitem.pub_date)
            .values("id", "oid", "title", "pub_date")
            .order_by("pub_date")[:1]
        ):
            next["categories"] = list(
                BlogItem.categories.through.objects.filter(
                    blogitem__id=next["id"]
                ).values_list("category__name", flat=True)
            )
            break
        else:
            next = None

        exclude_related = []
        if previous:
            post["previous_post"] = serialize_related(previous)
            exclude_related.append(previous["id"])
        if next:
            post["next_post"] = serialize_related(next)
            exclude_related.append(next["id"])

        related_by_category = get_related_posts_by_categories(
            blogitem, limit=4, exclude_ids=exclude_related
        )
        post["related_by_category"] = []
        for related_by in related_by_category:
            category_overlap_qs = get_category_overlap(blogitem, related_by)
            serialized_related = serialize_related(related_by)
            serialized_related["categories"] = list(
                category_overlap_qs.values_list("name", flat=True)
            )
            post["related_by_category"].append(serialized_related)

        related_by_keyword = []
        related_qs = get_related_posts_by_keyword(
            blogitem, limit=4, exclude_ids=exclude_related
        )
        related_by_keyword = list(related_qs)
        post["related_by_keyword"] = serialize_related_objects(related_by_keyword)

    blogcomments = BlogComment.objects.filter(blogitem=blogitem, approved=True)
    only = (
        "oid",
        "blogitem_id",
        "parent_id",
        "approved",
        "comment_rendered",
        "add_date",
        "name",
        "highlighted",
    )
    root_comments = (
        blogcomments.filter(parent__isnull=True).order_by("add_date").only(*only)
    )

    replies = blogcomments.filter(parent__isnull=False).order_by("add_date").only(*only)

    count_comments = count_approved_comments(blogitem.id)
    root_comments_count = count_approved_root_comments(blogitem.id)

    if page > 1:
        if (page - 1) * settings.MAX_RECENT_COMMENTS > root_comments_count:
            raise http.Http404("Gone too far")

    slice_m, slice_n = get_blogcomment_slice(root_comments_count, page)
    root_comments = root_comments[slice_m:slice_n]

    comments_truncated = False
    if root_comments_count > settings.MAX_RECENT_COMMENTS:
        comments_truncated = settings.MAX_RECENT_COMMENTS

    _values = (
        "id",
        "add_date",
        "parent_id",
        "oid",
        "name",
        "comment_rendered",
        "approved",
        "highlighted",
    )
    all_comments = defaultdict(list)
    for comment in root_comments.values(*_values):
        all_comments[comment["parent_id"]].append(comment)

    for comment in replies.values(*_values):
        all_comments[comment["parent_id"]].append(comment)

    total_pages = 1
    if isinstance(comments_truncated, int) and comments_truncated > 0:
        total_pages = math.ceil(root_comments_count / comments_truncated)
    total_pages = min(total_pages, settings.MAX_BLOGCOMMENT_PAGES)

    comments = {}
    comments["truncated"] = comments_truncated
    comments["count"] = count_comments
    comments["total_pages"] = total_pages
    comments["tree"] = traverse_and_serialize_comments(all_comments)
    _unhighlight_others(comments["tree"])

    comments["next_page"] = comments["previous_page"] = None
    if page < settings.MAX_BLOGCOMMENT_PAGES:
        # But is there even a next page?!
        if page * settings.MAX_RECENT_COMMENTS < root_comments_count:
            comments["next_page"] = page + 1
    if page > 1:
        comments["previous_page"] = page - 1

    context = {"post": post, "comments": comments}
    cache.set(cache_key, context, 5 if settings.DEBUG else 60 * 60 * 12)
    return http.JsonResponse(context)


def get_category_overlap(blogitem_base, blogitem):
    intersection = blogitem.categories.filter(id__in=blogitem_base.categories.all())
    return intersection.order_by("name")


def traverse_and_serialize_comments(all_comments, comment=None, depth=None):
    tree = []
    if not comment:
        iterator = all_comments[None]
    else:
        iterator = all_comments[comment["id"]]
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
    assert isinstance(blogcomment, dict)
    data = {
        "id": blogcomment["id"],
        "oid": blogcomment["oid"],
        "add_date": blogcomment["add_date"],
        "name": blogcomment["name"] or None,
        "comment": blogcomment["comment_rendered"],
        "approved": bool(blogcomment["approved"]),
    }
    if blogcomment["highlighted"]:
        data["highlighted"] = blogcomment["highlighted"]

    return data


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


def blogcomment(request, blogitem_oid, oid):
    only = (
        "id",
        "oid",
        "blogitem_id",
        "parent_id",
        "approved",
        "comment",
        "comment_rendered",
        "add_date",
        "name",
        "highlighted",
    )
    for comment in BlogComment.objects.filter(
        oid=oid, blogitem__oid=blogitem_oid, blogitem__hide_comments=False
    ).values(*only):
        for post in BlogItem.objects.filter(id=comment["blogitem_id"]).values(
            "oid",
            "title",
            "pub_date",
            "disallow_comments",
            "summary",
            "open_graph_image",
        ):
            break
        break
    else:
        return http.HttpResponseNotFound(oid)

    blogcomments = BlogComment.objects.filter(
        blogitem_id=comment["blogitem_id"], approved=True
    )

    page: int = _get_comment_page(comment)

    only = (
        "id",
        "oid",
        "blogitem_id",
        "parent_id",
        "approved",
        "comment",
        "comment_rendered",
        "add_date",
        "name",
    )

    all_comments = _get_replies_recursively(comment)

    root_comment = None
    if comment["parent_id"]:
        for root_comment in blogcomments.filter(id=comment["parent_id"]).values(*only):
            root_comment["depth"] = 0
            break

    comments = {}
    comments["truncated"] = False
    comments["count"] = 0
    comments["total_pages"] = 1
    comments["tree"] = traverse_and_serialize_comments(all_comments)
    comments["next_page"] = comments["previous_page"] = None

    comment_serialized = serialize_comment(comment)
    comment_serialized["depth"] = 0
    context = {
        "post": post,
        "replies": comments,
        "comment": comment_serialized,
        "parent": root_comment,
        "page": page,
    }
    return http.JsonResponse(context)


def _get_replies_recursively(comment, root=None, base_query=None):
    base_query = base_query or BlogComment.objects.filter(
        blogitem_id=comment["blogitem_id"], approved=True
    )
    _reply_values = (
        "add_date",
        "id",
        "oid",
        "parent_id",
        "name",
        "comment_rendered",
        "approved",
        "name",
        "highlighted",
    )
    replies = (
        base_query.filter(parent__oid=comment["oid"])
        .order_by("add_date")
        .values(*_reply_values)
    )
    all_comments = defaultdict(list)
    for reply in replies:
        all_comments[root].append(reply)
        all_comments.update(
            _get_replies_recursively(reply, root=reply["id"], base_query=base_query)
        )

    return all_comments


def _get_comment_page(comment: dict) -> int:
    base_query = BlogComment.objects.filter(
        blogitem_id=comment["blogitem_id"], approved=True
    )
    root_comment = comment
    while root_comment["parent_id"]:
        root_comment = base_query.values("id", "parent_id", "add_date").get(
            id=root_comment["parent_id"]
        )
    count = base_query.filter(
        add_date__gt=root_comment["add_date"],
        parent__isnull=True,
    ).count()
    return 1 + (count // settings.MAX_RECENT_COMMENTS)


def _unhighlight_others(comments_tree):
    highlighted = _traverse_highlights(comments_tree)
    if not highlighted:
        return

    highlighted.sort(key=lambda x: x[1], reverse=True)

    _traverse_unhighlight(comments_tree, highlighted[0][0])


def _traverse_highlights(comments_tree):
    highlighted: list[tuple[id, datetime.datetime]] = []
    for comment in comments_tree:
        if comment.get("highlighted"):
            highlighted.append((comment["id"], comment["highlighted"]))
        if comment.get("replies"):
            highlighted.extend(_traverse_highlights(comment["replies"]))

    return highlighted


def _traverse_unhighlight(comments_tree, exception_id):
    for comment in comments_tree:
        if comment.get("highlighted"):
            if comment["id"] != exception_id:
                del comment["highlighted"]
        if comment.get("replies"):
            _traverse_unhighlight(comment["replies"], exception_id)
