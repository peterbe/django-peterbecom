import datetime
import re
import time
from functools import lru_cache

from django import http
from django.conf import settings
from django.contrib.postgres.search import (
    SearchHeadline,
    SearchQuery,
    TrigramSimilarity,
)
from django.db import connection
from django.db.models import Q as Q_
from django.utils import timezone
from django.utils.cache import patch_cache_control
from django.views.decorators.cache import cache_control
from sentence_transformers import SentenceTransformer

from peterbecom.base.models import SearchResult
from peterbecom.homepage.utils import STOPWORDS, split_search
from peterbecom.plog.models import Category, SearchDoc, SearchTerm
from peterbecom.publicapi.forms import SearchForm


@lru_cache(maxsize=1)
def get_embedding_model():
    model = SentenceTransformer("all-mpnet-base-v2")
    return model


HIGHLIGHT_TYPE = "fvh"


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

    result = _typeahead(q, size)
    response = http.JsonResponse(
        {
            "results": result["results"],
            "meta": result["meta"],
        }
    )
    if len(q) < 5:
        patch_cache_control(response, public=True, max_age=60 + 60 * (5 - len(q)))
    return response


def _typeahead(term: str, size: int):
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

    if not results and len(term) >= 3:
        qs = base_qs.filter(term__trigram_similar=term.lower())
        qs = qs.values_list("term", flat=True).order_by("-popularity")[:size]
        for found_term in qs:
            results.append(
                {
                    "term": found_term,
                    "highlights": [_highlight_fuzzy_matches(term, found_term)],
                }
            )

        if not results:
            qs = base_qs.annotate(
                similarity=TrigramSimilarity("term", term),
            ).filter(similarity__gt=0.1)
            qs = qs.values_list("term", flat=True).order_by("-popularity")[:size]
            for found_term in qs:
                results.append(
                    {
                        "term": found_term,
                        "highlights": [_highlight_fuzzy_matches(term, found_term)],
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


def _highlight_fuzzy_matches(term: str, found_term: str) -> str:
    def html_escape(s: str) -> str:
        return (
            s.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )

    highlights_parts: list[str] = []
    for word in found_term.split():
        if _edit_distance(term, word) <= 2:
            highlights_parts.append(f"<mark>{html_escape(word)}</mark>")
        else:
            highlights_parts.append(word)

    return " ".join(highlights_parts)


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

    with_embeddings = False
    if q.startswith("embedded:"):
        q = q[len("embedded:") :].strip()
        with_embeddings = True

    search_results = _pg_search(
        q,
        popularity_factor,
        boost_mode,
        debug_search=debug,
        in_title_only=config.get("in_title"),
        no_fuzzy=config.get("no_fuzzy"),
        with_embeddings=with_embeddings,
    )

    context = {
        "q": q,
        "debug": debug,
        "original_q": original_q,
        # "count_documents": 0,
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


LIMIT_BLOG_ITEMS = 20
LIMIT_BLOG_COMMENTS = 10


def _pg_search(
    q,
    popularity_factor,
    boost_mode,
    debug_search=False,
    in_title_only=False,
    no_fuzzy=False,
    with_embeddings=False,
):
    keyword_search = {}
    search_times = []

    if with_embeddings:
        threshold = 0.4
        t0 = time.time()
        query_embedding = get_embedding_model().encode(q).tolist()
        search_times.append(("query_embedding", time.time() - t0))

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    oid,
                    title,
                    date,
                    popularity,
                    text,
                    categories,
                    1 - (title_embedding <=> %s::vector) AS title_similarity,
                    1 - (text_embedding <=> %s::vector) AS text_similarity
                FROM plog_searchdoc
                WHERE title_embedding IS NOT NULL and text_embedding IS NOT NULL
                AND (1 - (title_embedding <=> %s::vector) > %s OR 1 - (text_embedding <=> %s::vector) > %s)
                -- ORDER BY popularity DESC, title_similarity DESC, text_similarity DESC
                ORDER BY title_similarity DESC, text_similarity DESC
                LIMIT %s
            """,
                (
                    query_embedding,
                    query_embedding,
                    query_embedding,
                    threshold,
                    query_embedding,
                    threshold,
                    LIMIT_BLOG_ITEMS,
                ),
            )
            count = 0
            documents = []
            for result in cursor.fetchall():
                (
                    oid,
                    title,
                    date,
                    popularity,
                    text,
                    categories,
                    title_similarity,
                    text_similarity,
                ) = result
                document = {
                    "oid": oid,
                    "title": title,
                    "date": date,
                    "summary": text[:100],
                    "score": title_similarity + text_similarity,
                    "popularity": popularity or 0.0,
                    "comment": False,
                    "categories": categories,
                }
                documents.append(document)
                count += 1
            search_times.append(("query", time.time() - t0))
            print(f"Found {count} results with embeddings.")

            context = {
                "keywords": {},
                "count_documents": count,
                "documents": documents,
                "count_documents_shown": len(documents),
            }
            context["search_time"] = sum(x[1] for x in search_times)
            context["search_times"] = search_times

            return context

    if len(q) > 1:
        _keyword_keys = ("keyword", "keywords", "category", "categories")
        q, keyword_search = split_search(q, _keyword_keys)

    search_query = SearchDoc.objects.all().order_by("-popularity", "-date")

    if keyword_search.get("keyword"):
        search_query = search_query.filter(
            keywords__contains=[keyword_search["keyword"].lower()]
        )

    if keyword_search.get("category"):
        # This turns 'python' into 'Python'
        categories = []
        for name in Category.objects.filter(
            name__iexact=keyword_search["category"]
        ).values_list("name", flat=True):
            categories.append(name)
        search_query = search_query.filter(categories__contains=categories)

    title_search_query = _get_search_query(q)
    text_search_query = _get_search_query(q)

    search_query = search_query.annotate(
        title_headline=SearchHeadline(
            "title",
            title_search_query,
            start_sel="<mark>",
            stop_sel="</mark>",
        ),
        text_headline=SearchHeadline(
            "text",
            text_search_query,
            start_sel="<mark>",
            stop_sel="</mark>",
            max_fragments=2,
        ),
    )

    search_query_by_title = search_query.filter(title_search_vector=title_search_query)

    only = (
        "id",
        "oid",
        "title",
        "date",
        "text",
        "popularity",
        "categories",
        "title_headline",
        "text_headline",
    )

    t0 = time.time()
    results = list(search_query_by_title.values(*only)[: LIMIT_BLOG_ITEMS + 1])

    if len(results) > LIMIT_BLOG_ITEMS:
        count = search_query_by_title.count()
    else:
        count = len(results)
        found_by_title_ids = [r["id"] for r in results]

        if not in_title_only:
            search_query_by_text = search_query.filter(
                text_search_vector=text_search_query
            ).exclude(id__in=found_by_title_ids)
            text_results = list(search_query_by_text.values(*only)[:LIMIT_BLOG_ITEMS])

            results.extend(text_results)
            if len(text_results) > LIMIT_BLOG_ITEMS:
                count += search_query_by_text.count()
            else:
                count += len(text_results)

    t1 = time.time()
    search_times.append(("blogitems", t1 - t0))

    documents = []
    for result in results:
        title = result["title_headline"]
        summary = result["text_headline"]
        document = {
            "oid": result["oid"],
            "title": title,
            "date": result["date"],
            "summary": summary,
            "score": 0,
            "popularity": result["popularity"] or 0.0,
            "comment": False,
            "categories": result["categories"],
        }
        documents.append(document)

    context = {
        "keywords": keyword_search,
        "count_documents": count,
        "documents": documents,
        "count_documents_shown": len(documents),
    }
    context["search_time"] = sum(x[1] for x in search_times)
    context["search_times"] = search_times

    return context


synonyms = {
    ("js", "javascript"),
    ("py", "python"),
    ("python", "py"),
    ("react", "reactjs", "react.js"),
    ("node", "nodejs", "node.js"),
    ("nodejs", "node", "node.js"),
    ("node.js", "node", "nodejs"),
    ("postgres", "postgresql"),
    ("elastic", "elasticsearch"),
    ("pi", "π"),
}
_synonyms_map = {}
for group in synonyms:
    for term in group:
        _synonyms_map[term] = [t for t in group if t != term]


def _get_synonyms(term: str) -> list[str]:
    return _synonyms_map.get(term.lower(), [])


def _get_search_query(q: str) -> SearchQuery:
    if _is_perfectly_quoted(q):
        return SearchQuery(q[1:-1], search_type="phrase")

    qs = re.split(r"[\s-]+", q.lower())
    new_qs: list[str] = []
    for q in qs:
        if q not in new_qs:
            new_qs.append(q)
        for synonym in _get_synonyms(q):
            if synonym not in new_qs:
                new_qs.append(synonym)

    search_query = SearchQuery(new_qs[0])
    for q_ in new_qs[1:]:
        search_query |= SearchQuery(q_)
    return search_query


def _is_perfectly_quoted(q: str) -> bool:
    return len(q) >= 2 and q[0] == '"' and q[-1] == '"'
