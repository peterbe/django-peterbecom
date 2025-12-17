import datetime
import re
import time
from functools import reduce
from operator import or_

from django import http
from django.conf import settings
from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import Q as Q_
from django.utils import timezone
from django.utils.cache import patch_cache_control
from django.utils.html import strip_tags
from django.views.decorators.cache import cache_control
from elasticsearch_dsl import Q, query

from peterbecom.base.models import SearchResult
from peterbecom.homepage.utils import STOPWORDS, split_search
from peterbecom.plog.models import BlogItem, SearchTerm
from peterbecom.plog.search import BlogCommentDoc, BlogItemDoc, SearchTermDoc
from peterbecom.publicapi.forms import SearchForm

HIGHLIGHT_TYPE = "fvh"


def _get_highlights(hit, key, massage=False):
    highlights = []
    try:
        highlight = hit.meta.highlight
        for fragment in getattr(highlight, key, []):
            if massage:
                highlights.append(_massage_fragment(fragment))
            else:
                highlights.append(_clean_fragment_html(fragment))
    except AttributeError:
        print(f"No highlight called {key!r}")
        # Happens when there exists no highlights for this key.
        # Most likely it's when no indexer was used to match on it.
        # For example, if you...
        #
        #   Q("match", title={"query": query}) | Q("match", content={"query": query})
        #
        # But it never used the match on `content`.
        pass
    return highlights


@cache_control(max_age=settings.DEBUG and 6 or 60 * 60 * 12, public=True)
def typeahead(request):
    q = request.GET.get("q", "")
    if q.endswith("/") and len(q) > 1:
        q = q[:-1]
    if not q:
        return http.JsonResponse({"error": "Missing 'q'"}, status=400)
    if len(q) > 75:  # Arbitrary limit
        return http.JsonResponse({"error": "Too long"}, status=400)
    try:
        size = int(request.GET.get("n", 8))
        if size > 20:  # Arbitrary limit
            return http.JsonResponse({"error": "'n' too big"}, status=400)
    except ValueError:
        return http.JsonResponse({"error": "Invalid 'n'"}, status=400)

    pg = request.GET.get("pg") and request.GET.get("pg") not in ("no", "0", "")
    if pg:
        result = _typeahead_pg(q, size)
    else:
        result = _typeahead([q], size)
    response = http.JsonResponse(
        {
            "results": result["results"],
            "meta": result["meta"],
        }
    )
    if len(q) < 5:
        patch_cache_control(response, public=True, max_age=60 + 60 * (5 - len(q)))
    return response


def _typeahead(terms, size):
    assert terms
    all_suggestions = []
    search_query = SearchTermDoc.search(index=settings.ES_SEARCH_TERM_INDEX)

    qs = []

    assert isinstance(terms, list), type(terms)
    for term in terms:
        if _is_multiword_query(term):
            qs.append(
                Q(
                    "match_phrase_prefix",
                    term={"query": term, "boost": 10},
                )
            )
        qs.append(Q("match_bool_prefix", term={"query": term, "boost": 5}))
        if len(term) > 3:
            qs.append(
                Q("fuzzy", term={"value": term, "boost": 0.1, "fuzziness": "AUTO"})
            )

    query = reduce(or_, qs)

    search_query = search_query.query(query)

    search_query = _add_function_score(search_query, query)

    search_query = search_query[:size]

    search_query = search_query.highlight_options(
        pre_tags=["<mark>"], post_tags=["</mark>"]
    )
    search_query = search_query.highlight(
        "term",
        number_of_fragments=1,
        type=HIGHLIGHT_TYPE,
    )

    response = search_query.execute()
    results = []
    for hit in response.hits:
        highlights = _get_highlights(hit, "term")
        results.append(
            {
                "term": hit.term,
                "highlights": highlights,
            }
        )
    meta = {"found": response.hits.total.value, "took": response.took}

    return {
        "meta": meta,
        "results": results,
        "suggestions": all_suggestions,
    }


def _typeahead_pg(term: str, size: int):
    term = term.strip()
    assert term

    base_qs = SearchTerm.objects.all()
    if " " in term:
        qs = base_qs.filter(
            Q_(term__startswith=term.lower()) | Q_(term__contains=term.lower())
        )
    elif len(term) > 2:
        qs = base_qs.filter(
            Q_(term__startswith=term.lower()) | Q_(term__contains=f" {term.lower()}")
        )
    else:
        qs = base_qs.filter(term__startswith=term.lower())

    qs = qs.order_by("-popularity")[:size]

    results = []
    t0 = time.time()
    regex = re.compile(rf"\b({re.escape(term)}\w*)\b")
    for found_term in qs.values_list("term", flat=True):
        results.append(
            {
                "term": found_term,
                "highlights": [regex.sub(r"<mark>\1</mark>", found_term)],
            }
        )

    def html_escape(s: str) -> str:
        return (
            s.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )

    if not results and len(term) >= 3:
        qs = base_qs.annotate(
            similarity=TrigramSimilarity("term", term),
        ).filter(similarity__gt=0.1)
        qs = qs.values_list("term", flat=True).order_by("-popularity")[:size]
        for found_term in qs:
            highlights_parts: list[str] = []
            for word in found_term.split():
                if _edit_distance(term, word) <= 2:
                    highlights_parts.append(f"<mark>{html_escape(word)}</mark>")
                else:
                    highlights_parts.append(word)

            results.append(
                {
                    "term": found_term,
                    "highlights": [" ".join(highlights_parts)],
                }
            )

    t1 = time.time()

    if len(results) < size:
        count = len(results)
    else:
        count = qs.count()

    meta = {"found": count, "took": t1 - t0}

    return {
        "meta": meta,
        "results": results,
    }


def _edit_distance(s1: str, s2: str) -> int:
    """
    Calculates the Levenshtein edit distance between two strings.
    Edit distance is the minimum number of single-character edits
    (insertions, deletions or substitutions) required to change one string into the other.

    Args:
        s1 (str): First string.
        s2 (str): Second string.

    Returns:
        int: The edit distance between s1 and s2.
    """
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    # Initialize the table
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    # DP computation
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s1[i - 1] == s2[j - 1]:
                cost = 0
            else:
                cost = 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,  # deletion
                dp[i][j - 1] + 1,  # insertion
                dp[i - 1][j - 1] + cost,  # substitution
            )
    return dp[m][n]


@cache_control(max_age=settings.DEBUG and 6 or 60 * 60 * 12, public=True)
def search(request):
    form = SearchForm(request.GET)
    if not form.is_valid():
        return http.HttpResponseBadRequest(form.errors.as_json())

    q = original_q = form.cleaned_data["q"]
    config = form.cleaned_data["_config"]
    debug = form.cleaned_data["debug"]
    boost_mode = form.cleaned_data["boost_mode"] or settings.DEFAULT_BOOST_MODE
    popularity_factor = (
        form.cleaned_data["popularity_factor"] or settings.DEFAULT_POPULARITY_FACTOR
    )
    non_stopwords_q = [x for x in q.split() if x.lower() not in STOPWORDS]
    search_results = _search(
        q,
        popularity_factor,
        boost_mode,
        debug_search=debug,
        in_title_only=config.get("in_title"),
        no_fuzzy=config.get("no_fuzzy"),
    )
    context = {
        "q": q,
        "debug": debug,
        "original_q": original_q,
        "count_documents": 0,
        "results": search_results,
        "non_stopwords_q": non_stopwords_q,
        "config": config,
    }

    _save_search_result(q, original_q, search_results)

    return http.JsonResponse(context)


def _save_search_result(q, original_q, search_results):
    recently = timezone.now() - datetime.timedelta(minutes=1)
    recent_searches = SearchResult.objects.filter(q=q, created__gt=recently)
    if recent_searches.exists():
        print(f"Skip storing recent search for {q!r}")
        return

    SearchResult.objects.create(
        q=q,
        original_q=original_q,
        documents_found=search_results["count_documents"],
        search_time=datetime.timedelta(seconds=search_results["search_time"]),
        search_times=search_results["search_times"],
        keywords=search_results["keywords"],
    )


LIMIT_BLOG_ITEMS = 30
LIMIT_BLOG_COMMENTS = 20


def _search(
    q,
    popularity_factor,
    boost_mode,
    debug_search=False,
    in_title_only=False,
    no_fuzzy=False,
):
    documents = []
    search_times = []
    context = {}
    keyword_search = {}
    if len(q) > 1:
        # XXX Perhaps move this to SearchForm before the _search function.
        _keyword_keys = ("keyword", "keywords", "category", "categories")
        q, keyword_search = split_search(q, _keyword_keys)

    search_query = BlogItemDoc.search(index=settings.ES_BLOG_ITEM_INDEX)
    search_query.update_from_dict({"query": {"range": {"pub_date": {"lt": "now"}}}})

    if keyword_search.get("keyword"):
        search_query = search_query.filter(
            "terms", keywords=[keyword_search["keyword"]]
        )
    if keyword_search.get("category"):
        search_query = search_query.filter(
            "terms", categories=[keyword_search["category"]]
        )

    context["keywords"] = keyword_search

    matcher = None
    boost = 1 * 2
    boost_title = 2 * boost
    qs = []
    if _is_multiword_query(q):
        qs.append(Q("match_phrase", title={"query": q, "boost": boost_title * 3}))
        if not in_title_only:
            qs.append(Q("match_phrase", text={"query": q, "boost": boost * 2}))

    qs.append(Q("match", title={"query": q, "boost": boost_title}))
    if not in_title_only:
        qs.append(Q("match", text={"query": q, "boost": boost}))
    if len(q) > 3 and not no_fuzzy:
        qs.append(Q("fuzzy", title={"value": q, "boost": 0.2}))
        if len(q) > 5 and not in_title_only:
            qs.append(Q("fuzzy", text={"value": q, "boost": 0.1}))

    matcher = reduce(or_, qs)

    popularity_factor = settings.DEFAULT_POPULARITY_FACTOR
    boost_mode = settings.DEFAULT_BOOST_MODE

    assert isinstance(popularity_factor, float), repr(popularity_factor)

    search_query = _add_function_score(
        search_query, matcher, popularity_factor, boost_mode
    )

    search_query = search_query.highlight_options(
        pre_tags=["<mark>"], post_tags=["</mark>"]
    )

    if not in_title_only:
        search_query = search_query.highlight(
            "text", fragment_size=80, number_of_fragments=2, type=HIGHLIGHT_TYPE
        )
    search_query = search_query.highlight(
        "title", fragment_size=120, number_of_fragments=1, type=HIGHLIGHT_TYPE
    )

    search_query = search_query[:LIMIT_BLOG_ITEMS]

    t0 = time.time()
    response = search_query.execute()
    t1 = time.time()
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
                "oid": result["oid"],
                "title": title,
                "date": result["pub_date"],
                "summary": summary,
                "score": hit.meta.score,
                "popularity": hit.popularity or 0.0,
                "comment": False,
                "categories": result.get("categories") or [],
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

    if (
        context["count_documents"] < 10
        and not in_title_only
        and not keyword_search.get("category")
    ):
        # Now append the search results based on blog comments
        search_query = BlogCommentDoc.search(index=settings.ES_BLOG_COMMENT_INDEX)
        search_query = search_query.filter("term", approved=True)
        search_query = search_query.query("match_phrase", comment=q)

        search_query = search_query.highlight(
            "comment", fragment_size=80, number_of_fragments=2, type=HIGHLIGHT_TYPE
        )
        search_query = search_query.highlight_options(
            pre_tags=["<mark>"], post_tags=["</mark>"]
        )
        search_query = search_query[:LIMIT_BLOG_COMMENTS]
        t0 = time.time()
        response = search_query.execute()
        t1 = time.time()
        search_times.append(("blogcomments", t1 - t0))

        context["count_documents"] += response.hits.total.value

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
    context["search_times"] = search_times

    return context


def _is_multiword_query(query):
    return " " in query or "-" in query


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
