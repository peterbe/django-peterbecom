import re
import time

import meilisearch
from django import http
from django.conf import settings
from django.utils.cache import patch_cache_control
from django.utils.html import strip_tags
from django.views.decorators.cache import cache_control
from elasticsearch_dsl import Q, query
from elasticsearch_dsl.query import MultiMatch

from peterbecom.homepage.utils import STOPWORDS, split_search
from peterbecom.plog.models import BlogItem
from peterbecom.plog.search import BlogCommentDoc, BlogItemDoc
from peterbecom.publicapi.forms import SearchForm


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


@cache_control(max_age=settings.DEBUG and 60 or 60 * 60 * 12, public=True)
def search_meilisearch(request):
    form = SearchForm(request.GET)
    if not form.is_valid():
        return http.HttpResponseBadRequest(form.errors.as_json())

    q = original_q = form.cleaned_data["q"]
    debug = form.cleaned_data["debug"]
    # boost_mode = form.cleaned_data["boost_mode"] or settings.DEFAULT_BOOST_MODE
    # popularity_factor = (
    #     form.cleaned_data["popularity_factor"] or settings.DEFAULT_POPULARITY_FACTOR
    # )
    non_stopwords_q = [x for x in q.split() if x.lower() not in STOPWORDS]
    search_results = _meilisearch(q, debug_search=debug)
    context = {
        "q": q,
        "debug": debug,
        # "count_documents": 0,
        "original_q": original_q,
        "results": search_results,
        "non_stopwords_q": non_stopwords_q,
    }

    return http.JsonResponse(context)


def _meilisearch(q, debug_search=False, **kwargs):
    t0 = time.time()
    client = meilisearch.Client(settings.MEILISEARCH_URL)
    res = client.index("blogitems").search(
        q,
        {
            "attributesToHighlight": ["title", "text"],
            "attributesToRetrieve": ["oid", "pub_date", "popularity"],
            "hitsPerPage": LIMIT_BLOG_ITEMS,
            "highlightPreTag": "<mark>",
            "highlightPostTag": "</mark>",
            # "showMatchesPosition": True,
            "attributesToCrop": ["text"],
            "cropLength": 30,
        },
    )
    results = {"documents": []}
    results["count_documents"] = res.get("totalHits") or res["estimatedTotalHits"]
    results["took"] = res["processingTimeMs"]

    print("TOOK:", results["took"], "MEILISEARCH")

    for hit in res["hits"]:
        from pprint import pprint

        pprint(hit)
        title = hit["_formatted"]["title"]
        summary = hit["_formatted"]["text"]
        document = {
            "oid": hit["oid"],
            "title": title,
            "date": hit["pub_date"],
            # "comment": False,
            "popularity": hit["popularity"],
            "summary": summary,
            "score": 0.0,
        }
        results["documents"].append(document)

    t2 = time.time()
    results["count_documents_shown"] = len(results["documents"])
    results["search_time"] = t2 - t0

    return results


@cache_control(max_age=settings.DEBUG and 6 or 60 * 60 * 12, public=True)
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
    non_stopwords_q = [x for x in q.split() if x.lower() not in STOPWORDS]
    if request.GET.get("meilisearch") == "true":
        search_results = _meilisearch(
            q,
            popularity_factor=popularity_factor,
            boost_mode=boost_mode,
            debug_search=debug,
        )
    else:
        search_results = _search(q, popularity_factor, boost_mode, debug_search=debug)
    context = {
        "q": q,
        "debug": debug,
        "original_q": original_q,
        # "count_documents": 0,
        "results": search_results,
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

    print("TOOK", response.took, "ELASTICSEARCH")
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
    search_query = BlogCommentDoc.search(index=settings.ES_BLOG_COMMENT_INDEX)
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
        return _search(
            q,
            popularity_factor,
            boost_mode,
            debug_search=debug_search,
            strategy="match",
        )

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
