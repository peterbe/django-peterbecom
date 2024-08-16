import datetime
import re
import time
from functools import reduce
from operator import or_

from django import http
from django.conf import settings
from django.utils import timezone
from django.utils.cache import patch_cache_control
from django.utils.html import strip_tags
from django.views.decorators.cache import cache_control
from elasticsearch_dsl import Q, query
from elasticsearch_dsl.query import MultiMatch

from peterbecom.base.models import SearchResult
from peterbecom.homepage.utils import STOPWORDS, split_search
from peterbecom.plog.models import BlogItem
from peterbecom.plog.search import BlogCommentDoc, BlogItemDoc, SearchTermDoc
from peterbecom.publicapi.forms import SearchForm

HIGHLIGHT_TYPE = "fvh"


def autocompete(request):
    q = request.GET.get("q", "")
    if not q:
        return http.JsonResponse({"error": "Missing 'q'"}, status=400)
    size = int(request.GET.get("n", 10))
    terms = [q]
    search_query = BlogItemDoc.search(index=settings.ES_BLOG_ITEM_INDEX)
    if len(q) > 2:
        suggestion = search_query.suggest("suggestions", q, term={"field": "title"})
        response = suggestion.execute()
        suggestions = response.suggest.suggestions
        for suggestion in suggestions:
            for option in suggestion.options:
                terms.append(q.replace(suggestion.text, option.text))

    search_query.update_from_dict({"query": {"range": {"pub_date": {"lt": "now"}}}})

    query = MultiMatch(
        query=terms[0],
        type="bool_prefix",
        fields=[
            "title_autocomplete",
            "title_autocomplete._2gram",
            "title_autocomplete._3gram",
        ],
    )

    for term in terms[1:]:
        query |= MultiMatch(
            query=term,
            type="bool_prefix",
            fields=[
                "title_autocomplete",
                "title_autocomplete._2gram",
                # Commented out because sometimes the `terms[:1]` are a little bit
                # too wild.
                # What might be a better idea is to make 2 ES queries. One with
                # `term[0]` and if that yields less than $batch_size, we make
                # another query with the `terms[1:]` and append the results.
                # "title_autocomplete._3gram",
            ],
        )

    search_query = search_query.query(query)

    # search_query = search_query.sort("-pub_date", "_score")
    search_query = _add_function_score(search_query, query)
    search_query = search_query[:size]
    response = search_query.execute()
    results = []
    for hit in response.hits:
        results.append([f"/plog/{hit.oid}", hit.title])

    response = http.JsonResponse({"results": results, "terms": terms})
    if len(q) < 5:
        patch_cache_control(response, public=True, max_age=60 + 60 * (5 - len(q)))
    return response


def autocomplete(request):
    q = request.GET.get("q", "")
    if q.endswith("/") and len(q) > 1:
        q = q[:-1]
    if not q:
        return http.JsonResponse({"error": "Missing 'q'"}, status=400)
    size = int(request.GET.get("n", 10))
    result = _autocomplete([q], size, suggest=len(q) > 4)
    if len(result["results"]) < size and result["suggestions"]:
        print("Suggest", result["suggestions"])
        suggestions = _autocomplete(
            result["suggestions"], size - len(result["results"]), suggest=False
        )
        already = set(x["oid"] for x in result["results"])
        additional = [x for x in suggestions["results"] if x["oid"] not in already]
        result["results"].extend(additional[: size - len(result["results"])])
        result["meta"]["found"] += len(additional)

    response = http.JsonResponse(
        {
            "results": result["results"],
            "meta": result["meta"],
        }
    )
    if len(q) < 5:
        patch_cache_control(response, public=True, max_age=60 + 60 * (5 - len(q)))
    return response


def _autocomplete(terms, size, suggest=False):
    assert terms
    all_suggestions = []
    search_query = BlogItemDoc.search(index=settings.ES_BLOG_ITEM_INDEX)
    if suggest:
        suggestion = search_query.suggest(
            "suggestions", terms[0], term={"field": "title"}
        )
        response = suggestion.execute()
        suggestions = response.suggest.suggestions
        for suggestion in suggestions:
            for option in suggestion.options:
                all_suggestions.append(terms[0].replace(suggestion.text, option.text))

    qs = []

    for term in terms:
        if _is_multiword_query(term):
            qs.append(
                Q(
                    "match_phrase_prefix",
                    title={"query": term, "boost": 4},
                )
            )
        qs.append(Q("match_bool_prefix", title={"query": term, "boost": 2}))
        if suggest:
            qs.append(
                Q(
                    "fuzzy",
                    title={
                        "value": term,
                        "boost": 0.1,
                        "fuzziness": "AUTO",
                        "prefix_length": 2,
                    },
                )
            )
    query = reduce(or_, qs)

    search_query = search_query.query(query)

    search_query = _add_function_score(search_query, query)
    search_query = search_query[:size]

    search_query = search_query.highlight_options(
        pre_tags=["<mark>"], post_tags=["</mark>"]
    )
    search_query = search_query.highlight(
        "title",
        fragment_size=200,
        no_match_size=200,
        number_of_fragments=3,
        type=HIGHLIGHT_TYPE,
    )

    response = search_query.execute()
    results = []
    for hit in response.hits:
        title_highlights = _get_highlights(hit, "title")
        results.append(
            {
                "oid": hit.oid,
                "title": title_highlights and title_highlights[0] or hit.title,
                "date": hit.pub_date,
            }
        )

    meta = {"found": response.hits.total.value, "took": response.took}

    return {
        "meta": meta,
        "results": results,
        "suggestions": all_suggestions,
    }


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
