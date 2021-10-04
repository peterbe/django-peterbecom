import re
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
from django.utils.html import strip_tags
from elasticsearch_dsl import Q, query

from peterbecom.base.utils import fake_ip_address
from peterbecom.plog.models import BlogComment, BlogItem, Category
from peterbecom.plog.spamprevention import (
    contains_spam_patterns,
    contains_spam_url_patterns,
    is_trash_commenter,
)
from peterbecom.plog.tasks import send_new_comment_email
from peterbecom.plog.utils import render_comment_text
from peterbecom.publicapi.forms import SubmitForm, SearchForm
from peterbecom.homepage.utils import make_categories_q, STOPWORDS, split_search
from peterbecom.plog.search import BlogCommentDoc, BlogItemDoc


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

    print("BLOGITEM:", repr(blogitem))

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
            }
        return {
            "oid": post_object.oid,
            "title": post_object.title,
            "pub_date": post_object.pub_date,
        }

    def serialize_related_objects(post_objects):
        return [serialize_related(x) for x in post_objects]

    post["previous_post"] = post["next_post"] = None

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
            post["previous_post"] = serialize_related(previous)
            exclude_related.append(previous.id)
        if next:
            post["next_post"] = serialize_related(next)
            exclude_related.append(next.id)

        related_by_category = get_related_posts_by_categories(
            blogitem, limit=5, exclude_ids=exclude_related
        )
        post["related_by_category"] = []
        for related_by in related_by_category:
            category_overlap_qs = get_category_overlap(blogitem, related_by)
            serialized_related = serialize_related(related_by)
            serialized_related["categories"] = list(
                category_overlap_qs.values_list("name", flat=True)
            )
            post["related_by_category"].append(serialized_related)

        related_by_keyword = list(
            get_related_posts_by_keyword(
                blogitem, limit=5, exclude_ids=exclude_related
            ).values("id", "oid", "title", "pub_date")
        )
        post["related_by_keyword"] = serialize_related_objects(related_by_keyword)

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

    comments["next_page"] = comments["previous_page"] = None
    if page < settings.MAX_BLOGCOMMENT_PAGES:
        # But is there even a next page?!
        if page * settings.MAX_RECENT_COMMENTS < root_comments_count:
            comments["next_page"] = page + 1
    if page > 1:
        comments["previous_page"] = page - 1

    return http.JsonResponse({"post": post, "comments": comments})


def get_category_overlap(blogitem_base, blogitem):
    intersection = blogitem.categories.filter(id__in=blogitem_base.categories.all())
    return intersection.order_by("name")


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


def homepage_blogitems(request):
    context = {}
    try:
        page = int(request.GET.get("page") or "1")
        if page <= 0:
            raise ValueError()
    except ValueError:
        return http.HttpResponseBadRequest("invalid page")

    qs = BlogItem.objects.filter(pub_date__lt=timezone.now(), archived__isnull=True)

    ocs = request.GET.getlist("oc")
    if ocs:
        categories = []
        for oc in ocs:
            try:
                categories.append(Category.objects.get(name=oc))
            except Category.DoesNotExist:
                return http.HttpResponseBadRequest(f"invalid oc {oc!r}")

        cat_q = make_categories_q(categories)
        qs = qs.filter(cat_q)

    if request.method == "HEAD":
        return http.HttpResponse("")

    batch_size = settings.HOMEPAGE_BATCH_SIZE
    page = page - 1
    n, m = page * batch_size, (page + 1) * batch_size
    max_count = qs.count()
    if page * batch_size > max_count:
        return http.HttpResponseNotFound("Too far back in time")

    if (page + 1) * batch_size < max_count:
        context["next_page"] = page + 2
    else:
        context["next_page"] = None

    if page >= 1:
        context["previous_page"] = page
    else:
        context["previous_page"] = None

    blogitems = (qs.prefetch_related("categories").order_by("-pub_date"))[n:m]

    approved_comments_count = {}
    blog_comments_count_qs = (
        BlogComment.objects.filter(blogitem__in=blogitems, approved=True)
        .values("blogitem_id")
        .annotate(count=Count("blogitem_id"))
    )
    for count in blog_comments_count_qs:
        approved_comments_count[count["blogitem_id"]] = count["count"]

    context["posts"] = []
    # XXX can be optimized to use .values()
    for blogitem in blogitems:
        context["posts"].append(
            {
                "oid": blogitem.oid,
                "title": blogitem.title,
                "comments": approved_comments_count.get(blogitem.id) or 0,
                "categories": [x.name for x in blogitem.categories.all()],
                "html": blogitem.text_rendered,
            }
        )

    return http.JsonResponse(context)


def search(request):
    form = SearchForm(request.GET)
    if not form.is_valid():
        return http.HttpResponseBadRequest(form.errors.as_json())

    q = original_q = form.cleaned_data["q"]
    debug = form.cleaned_data["debug"]
    boost_mode = form.cleaned_data["boost_mode"] or settings.DEFAULT_BOOST_MODE
    popularity_factor = (
        form.cleaned_data["popularity_factor"] or settings.DEFAULT_POPULARITY_FACTOR
    )
    # t0 = time.time()

    non_stopwords_q = [x for x in q.split() if x.lower() not in STOPWORDS]

    search_results = _search(q, popularity_factor, boost_mode, debug_search=debug)
    # t1 = time.time()
    # search_time = t1 - t0

    print({"q": q, "debug": debug})
    context = {
        "q": q,
        "debug": debug,
        "original_q": original_q,
        "count_documents": 0,
        "results": search_results,
        # "search_time": search_time,
        # "keywords": keywoards,
        "non_stopwords_q": non_stopwords_q,
    }

    return http.JsonResponse(context)


LIMIT_BLOG_ITEMS = 30
LIMIT_BLOG_COMMENTS = 20


def _search(
    q,
    popularity_factor,
    boost_mode,
    debug_search=False,
    strategy="match_phrase",
):
    documents = []
    search_times = []
    context = {}
    keyword_search = {}
    if len(q) > 1:
        _keyword_keys = ("keyword", "keywords", "category", "categories")
        q, keyword_search = split_search(q, _keyword_keys)

    search_terms = [(1.1, q)]
    _search_terms = set([q])
    doc_type_keys = ((BlogItemDoc, ("title", "text")), (BlogCommentDoc, ("comment",)))
    for doc_type, keys in doc_type_keys:
        suggester = doc_type.search()
        for key in keys:
            suggester = suggester.suggest("sugg", q, term={"field": key})
        suggestions = suggester.execute()
        for each in suggestions.suggest.sugg:
            if each.options:
                for option in each.options:
                    if option.score >= 0.6:
                        better = q.replace(each["text"], option["text"])
                        if better not in _search_terms:
                            search_terms.append((option["score"], better))
                            _search_terms.add(better)

    search_query = BlogItemDoc.search()
    search_query.update_from_dict({"query": {"range": {"pub_date": {"lt": "now"}}}})

    if keyword_search.get("keyword"):
        search_query = search_query.filter(
            "terms", keywords=[keyword_search["keyword"]]
        )
    if keyword_search.get("category"):
        search_query = search_query.filter(
            "terms", categories=[keyword_search["category"]]
        )

    matcher = None
    search_terms.sort(reverse=True)
    max_search_terms = 5  # to not send too much stuff to ES
    if len(search_terms) > max_search_terms:
        search_terms = search_terms[:max_search_terms]

    # strategy = "match_phrase"
    # if original_q:
    #     strategy = "match"
    search_term_boosts = {}
    for i, (score, word) in enumerate(search_terms):
        # meaning the first search_term should be boosted most
        j = len(search_terms) - i
        boost = 1 * j * score
        boost_title = 2 * boost
        search_term_boosts[word] = (boost_title, boost)
        match = Q(strategy, title={"query": word, "boost": boost_title}) | Q(
            strategy, text={"query": word, "boost": boost}
        )
        if matcher is None:
            matcher = match
        else:
            matcher |= match

    context["search_terms"] = search_terms
    context["search_term_boosts"] = search_term_boosts

    popularity_factor = settings.DEFAULT_POPULARITY_FACTOR
    boost_mode = settings.DEFAULT_BOOST_MODE

    # if debug_search:
    #     context["debug_search_form"] = DebugSearchForm(
    #         request.GET,
    #         initial={
    #             "popularity_factor": settings.DEFAULT_POPULARITY_FACTOR,
    #             "boost_mode": settings.DEFAULT_BOOST_MODE,
    #         },
    #     )
    #     if context["debug_search_form"].is_valid():
    #         popularity_factor = context["debug_search_form"].cleaned_data[
    #             "popularity_factor"
    #         ]
    #         boost_mode = context["debug_search_form"].cleaned_data["boost_mode"]

    assert isinstance(popularity_factor, float), repr(popularity_factor)

    search_query = _add_function_score(
        search_query, matcher, popularity_factor, boost_mode
    )

    search_query = search_query.highlight_options(
        pre_tags=["<mark>"], post_tags=["</mark>"]
    )

    search_query = search_query.highlight(
        "text", fragment_size=80, number_of_fragments=2, type="plain"
    )
    search_query = search_query.highlight(
        "title", fragment_size=120, number_of_fragments=1, type="plain"
    )

    search_query = search_query[:LIMIT_BLOG_ITEMS]
    t0 = time.time()
    response = search_query.execute()
    t1 = time.time()
    # print("TOOK", response.took)
    search_times.append(("blogitems", t1 - t0))

    for hit in response:
        result = hit.to_dict()
        try:
            for fragment in hit.meta.highlight.title:
                title = _clean_fragment_html(fragment)
        except AttributeError:
            title = _clean_fragment_html(result["title"])
        texts = []
        try:
            for fragment in hit.meta.highlight.text:
                texts.append(_massage_fragment(fragment))
        except AttributeError:
            texts.append(strip_tags(result["text"])[:100] + "...")
        summary = "<br>".join(texts)
        documents.append(
            {
                # "url": reverse("blog_post", args=(result["oid"],)),
                "oid": result["oid"],
                "title": title,
                "date": result["pub_date"],
                "summary": summary,
                "score": hit.meta.score,
                "popularity": hit.popularity or 0.0,
                "comment": False,
            }
        )

    if debug_search:
        ranked_by_popularity = [
            x["oid"]
            for x in sorted(documents, key=lambda x: x["popularity"], reverse=True)
        ]
        for i, document in enumerate(documents):
            document["score_boosted"] = ranked_by_popularity.index(document["oid"]) - i
            document["popularity_ranking"] = 1 + ranked_by_popularity.index(
                document["oid"]
            )

    context["count_documents"] = response.hits.total.value

    # Now append the search results based on blog comments
    search_query = BlogCommentDoc.search()
    search_query = search_query.filter("term", approved=True)
    search_query = search_query.query("match_phrase", comment=q)

    search_query = search_query.highlight(
        "comment", fragment_size=80, number_of_fragments=2, type="plain"
    )
    search_query = search_query.highlight_options(
        pre_tags=["<mark>"], post_tags=["</mark>"]
    )
    search_query = search_query[:LIMIT_BLOG_COMMENTS]
    t0 = time.time()
    response = search_query.execute()
    t1 = time.time()
    # print("TOOK", response.took)
    search_times.append(("blogcomments", t1 - t0))

    context["count_documents"] += response.hits.total.value

    if strategy != "match" and not context["count_documents"] and " " in q:
        # recurse
        return _search(q, debug_search=debug_search, strategy="match")
        # return search(q=q, original_q=q, debug_search=debug_search)

    blogitem_lookups = set()
    for hit in response:
        result = hit.to_dict()
        texts = []
        try:
            for fragment in hit.meta.highlight.comment:
                texts.append(_massage_fragment(fragment))
        except AttributeError:
            texts.append(strip_tags(result["comment"])[:100] + "...")
        summary = "<br>".join(texts)
        blogitem_lookups.add(result["blogitem_id"])
        documents.append(
            {
                "_id": result["blogitem_id"],
                # "title": None,
                "date": result["add_date"],
                "summary": summary,
                "score": hit.meta.score,
                "comment_oid": result["oid"],
                # "oid": result["oid"],
            }
        )

    if blogitem_lookups:
        blogitems = {}
        blogitem_qs = BlogItem.objects.filter(id__in=blogitem_lookups)
        for blog_item in blogitem_qs.values("id", "title", "oid"):
            blogitems[blog_item["id"]] = {
                "title": (
                    f"Comment on <i>{_clean_fragment_html(blog_item['title'])}</i>"
                ),
                "oid": blog_item["oid"],
            }
        for doc in documents:
            _id = doc.pop("_id", None)
            if _id:
                doc["oid"] = blogitems[_id]["oid"]
                doc["title"] = blogitems[_id]["title"]
                # if doc["comment"]:
                #     doc["url"] += "#{}".format(doc["oid"])

    context["documents"] = documents
    context["count_documents_shown"] = len(documents)

    context["search_time"] = sum(x[1] for x in search_times)

    return context


def _add_function_score(
    search_query,
    matcher,
    popularity_factor=settings.DEFAULT_POPULARITY_FACTOR,
    boost_mode=settings.DEFAULT_BOOST_MODE,
):
    # If you don't do any popularity sorting at all, the _score is entirely based
    # in the scoring that Elasticsearch gives which is a function of the boosting
    # between title and text and a function of how much the words appear and stuff.
    # A great score would be something like 10.0.
    if not popularity_factor:
        return search_query.query(matcher)

    # XXX Might be worth playing with a custom scoring function that uses
    # `score + popularity * factor` so that documents with a tiny popularity
    # doesn't completely ruin the total score.
    return search_query.query(
        "function_score",
        query=matcher,
        functions=[
            query.SF(
                "field_value_factor",
                field="popularity",
                factor=popularity_factor,
                # You can't sort on fields if they have nulls in them, so this
                # "fills in the blanks" by assigning nulls to be 0.0.
                missing=0.0,
            )
        ],
        boost_mode=boost_mode,
    )


def _massage_fragment(text, max_length=300):
    while len(text) > max_length:
        split = text.split()
        d_left = text.find("<mark>")
        d_right = len(text) - text.rfind("</mark>")
        if d_left > d_right:
            # there's more non-<mark> on the left
            split = split[1:]
        else:
            split = split[:-1]
        text = " ".join(split)
    text = text.strip()
    if not text.endswith("."):
        text += "…"
    text = text.lstrip(", ")
    text = text.lstrip(". ")
    uppercase = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    if text[0] not in uppercase:
        text = "…" + text
    text = _htmlify_text(text, newline_to_br=False, allow=("mark",))
    text = text.replace("</mark> <mark>", " ")
    return text


def _htmlify_text(text, newline_to_br=True, allow=()):
    allow_ = []
    for each in allow:
        allow_.append("<{}>".format(each))
        allow_.append("</{}>".format(each))

    def replacer(match):
        group = match.group()
        if group in allow_:
            # let it be
            return group
        return ""

    html = re.sub(r"<.*?>", replacer, text)
    if newline_to_br:
        html = html.replace("\n", "<br/>")
    return html


def _clean_fragment_html(fragment):
    def replacer(match):
        group = match.group()
        if group in ("<mark>", "</mark>"):
            return group
        return ""

    _html_regex = re.compile(r"<.*?>")
    fragment = _html_regex.sub(replacer, fragment)
    return fragment.replace("</mark> <mark>", " ")
