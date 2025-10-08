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

    comment_oid = request.GET.get("comment")

    cache_key = f"publicapi_blogitem_{oid}:{page}:{comment_oid}"
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

    _values = (
        "id",
        "add_date",
        "parent_id",
        "oid",
        "name",
        "comment_rendered",
        "approved",
    )

    comment: dict | None = None
    if comment_oid:
        for comment in BlogComment.objects.filter(
            oid=comment_oid, blogitem=blogitem
        ).values(*_values):
            if not comment["approved"]:
                return http.HttpResponseNotFound("comment not found")
            break
        else:
            return http.HttpResponseNotFound(comment_oid)

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

    if comment:
        pass
    elif blogitem.oid != "blogitem-040601-1":
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

    only = (
        "oid",
        "blogitem_id",
        "parent_id",
        "approved",
        "comment_rendered",
        "add_date",
        "name",
    )
    blogcomments_base = BlogComment.objects.filter(blogitem=blogitem, approved=True)
    if comment:
        # parent_comment = None  # XXX
        # count_replies = 0 # XXX

        # To figure out which page this belongs to, we need count how many root
        # comments there are before this comment.
        # parent_comment = comment["parent_id"]
        # this_comment = copy.copy(comment)
        root_comment = comment
        # print("0000")
        # from pprint import pprint

        # pprint(root_comment)
        while root_comment["parent_id"]:
            root_comment = BlogComment.objects.values(*_values).get(
                id=root_comment["parent_id"]
            )
            # print("1111")
            # pprint(root_comment)
            # print("\n")

            # found = False
            # print("111", root_comment)
            # for other_comment in BlogComment.objects.filter(
            #     oid=root_comment["parent_id"], blogitem=blogitem
            # ).values(*_values):
            #     if comment["approved"]:
            #         root_comment = other_comment
            #         # found = True
            #         break
            # # if found:
            # #     break

        # print("THIS COMMENT", repr(comment))
        # print("ROOT COMMENT", repr(root_comment))
        count_after = blogcomments_base.filter(
            add_date__gt=root_comment["add_date"],
            parent__isnull=True,
        ).count()
        print(
            "COUNT AFTER",
            count_after,
            "settings.MAX_RECENT_COMMENTS",
            settings.MAX_RECENT_COMMENTS,
        )
        page = 1 + (count_after // settings.MAX_RECENT_COMMENTS)
        # print("PAGE", page)

        comments = {}
        comments["truncated"] = False
        comments["count"] = 0
        comments["total_pages"] = 1
        comments["tree"] = []  # serialize_comment(comment) for comment in replies]
        comments["next_page"] = comments["previous_page"] = None

        comment = serialize_comment(comment)
        comment["depth"] = 0

    else:
        root_comments = (
            blogcomments_base.filter(parent__isnull=True)
            .order_by("add_date")
            .only(*only)
        )

        replies = (
            blogcomments_base.filter(parent__isnull=False)
            .order_by("add_date")
            .only(*only)
        )

        count_comments = count_approved_comments(blogitem.id)
        root_comments_count = count_approved_root_comments(blogitem.id)

        if page > 1:
            if (page - 1) * settings.MAX_RECENT_COMMENTS > root_comments_count:
                raise http.Http404("Gone too far")

        slice_m, slice_n = get_blogcomment_slice(root_comments_count, page)
        root_comments = root_comments[slice_m:slice_n]

        comments_truncated: bool | int = False
        if root_comments_count > settings.MAX_RECENT_COMMENTS:
            comments_truncated = settings.MAX_RECENT_COMMENTS

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

        comments["next_page"] = comments["previous_page"] = None
        if page < settings.MAX_BLOGCOMMENT_PAGES:
            # But is there even a next page?!
            if page * settings.MAX_RECENT_COMMENTS < root_comments_count:
                comments["next_page"] = page + 1
        if page > 1:
            comments["previous_page"] = page - 1

        comment = None

    context = {"post": post, "comments": comments, "comment": comment, "page": page}
    cache.set(cache_key, context, 10 if settings.DEBUG else 60 * 60 * 12)
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
    if isinstance(blogcomment, dict):
        return {
            "id": blogcomment["id"],
            "oid": blogcomment["oid"],
            "add_date": blogcomment["add_date"],
            "name": blogcomment["name"] or None,
            "comment": blogcomment["comment_rendered"],
            "approved": bool(blogcomment["approved"]),
        }
    else:
        raise Exception("/????")
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
