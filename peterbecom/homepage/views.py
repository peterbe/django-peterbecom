import datetime
import re
import os
import time
import logging
import random
from pathlib import Path
from urllib.parse import urlencode

from elasticsearch_dsl import Q
from huey.contrib.djhuey import task

from django import http
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST
from django.db.models import Count
from django.urls import reverse
from django.contrib.sites.requests import RequestSite
from django.views.decorators.cache import cache_control
from django.contrib.auth import logout
from django.conf import settings
from django.utils.html import strip_tags
from django.views import static

from peterbecom.base.models import SearchResult
from peterbecom.base.decorators import variable_cache_control
from peterbecom.plog.models import BlogItem, BlogComment
from peterbecom.plog.utils import utc_now, view_function_timer
from .utils import parse_ocs_to_categories, make_categories_q, split_search, STOPWORDS
from fancy_cache import cache_page
# from peterbecom.plog.utils import make_prefix
from peterbecom.plog.search import BlogItemDoc, BlogCommentDoc


logger = logging.getLogger("homepage")


ONE_HOUR = 60 * 60
ONE_DAY = ONE_HOUR * 24
ONE_WEEK = ONE_DAY * 7
ONE_MONTH = ONE_WEEK * 4


def _home_cache_max_age(request, oc=None, page=1):
    max_age = ONE_HOUR
    if oc:
        max_age *= 10
    if page:
        try:
            if int(page) > 1:
                max_age *= 2
        except ValueError:
            return 0

    # Add some jitter to avoid all pages to expire at the same time
    # if the cache is ever reset.
    p = random.randint(0, 25) / 100
    max_age += int(max_age * p)

    return max_age


@variable_cache_control(public=True, max_age=_home_cache_max_age)
def home(request, oc=None, page=1):
    context = {}
    qs = BlogItem.objects.filter(pub_date__lt=utc_now())
    if oc is not None:
        if not oc:  # empty string
            return redirect("/", permanent=True)
        categories = parse_ocs_to_categories(oc, strict_matching=True)
        cat_q = make_categories_q(categories)
        qs = qs.filter(cat_q)
        context["categories"] = categories

    # Reasons for not being here
    if request.method == "HEAD":
        return http.HttpResponse("")

    batch_size = settings.HOMEPAGE_BATCH_SIZE

    try:
        page = max(1, int(page)) - 1
    except ValueError:
        raise http.Http404("invalid page value")
    n, m = page * batch_size, (page + 1) * batch_size
    max_count = qs.count()
    if page * batch_size > max_count:
        return http.HttpResponse("Too far back in time\n", status=404)
    if (page + 1) * batch_size < max_count:
        context["next_page"] = page + 2
    context["previous_page"] = page

    # If you're going deep into the pagination with some really old
    # pages, it's not worth using the fs cache because if you have to
    # store a fs cache version for every single page from p5 to p55
    # it's too likely to get stale and old and it's too much work
    # on the mincss postprocess.
    if page > 6 or (context.get("categories") and page > 2):
        request._fscache_disable = True

    if context.get("categories"):
        oc_path = "/".join(["oc-{}".format(c.name) for c in context["categories"]])
        oc_path = oc_path[3:]

    if context.get("next_page"):
        if context.get("categories"):
            next_page_url = reverse(
                "only_category_paged", args=(oc_path, context["next_page"])
            )
        else:
            next_page_url = reverse("home_paged", args=(context["next_page"],))
        context["next_page_url"] = next_page_url

    if context["previous_page"] > 1:
        if context.get("categories"):
            previous_page_url = reverse(
                "only_category_paged", args=(oc_path, context["previous_page"])
            )
        else:
            previous_page_url = reverse("home_paged", args=(context["previous_page"],))
        context["previous_page_url"] = previous_page_url
    elif context["previous_page"]:  # i.e. == 1
        if context.get("categories"):
            previous_page_url = reverse("only_category", args=(oc_path,))
        else:
            previous_page_url = "/"
        context["previous_page_url"] = previous_page_url

    context["blogitems"] = (qs.prefetch_related("categories").order_by("-pub_date"))[
        n:m
    ]

    if page > 0:  # page starts on 0
        context["page_title"] = "Page {}".format(page + 1)

    approved_comments_count = {}
    blog_comments_count_qs = (
        BlogComment.objects.filter(blogitem__in=context["blogitems"], approved=True)
        .values("blogitem_id")
        .annotate(count=Count("blogitem_id"))
    )
    for count in blog_comments_count_qs:
        approved_comments_count[count["blogitem_id"]] = count["count"]
    context["approved_comments_count"] = approved_comments_count

    return render(request, "homepage/home.html", context)


_uppercase = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
_html_regex = re.compile(r"<.*?>")


def htmlify_text(text, newline_to_br=True, allow=()):
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

    html = _html_regex.sub(replacer, text)
    if newline_to_br:
        html = html.replace("\n", "<br/>")
    return html


def massage_fragment(text, max_length=300):
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
    if text[0] not in _uppercase:
        text = "…" + text
    text = htmlify_text(text, newline_to_br=False, allow=("mark",))
    text = text.replace("</mark> <mark>", " ")
    return text


def clean_fragment_html(fragment):
    def replacer(match):
        group = match.group()
        if group in ("<mark>", "</mark>"):
            return group
        return ""

    fragment = _html_regex.sub(replacer, fragment)
    return fragment.replace("</mark> <mark>", " ")


@view_function_timer()
def search(request, original_q=None):
    context = {}
    q = request.GET.get("q", "")
    if len(q) > 90:
        return http.HttpResponse("Search too long")

    LIMIT_BLOG_ITEMS = 30
    LIMIT_BLOG_COMMENTS = 20

    documents = []
    search_times = []
    context["base_url"] = "https://%s" % RequestSite(request).domain

    context["q"] = q

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

    strategy = "match_phrase"
    if original_q:
        strategy = "match"
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

    search_query = search_query.query(matcher)

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
    search_times.append(("blogitems", t1 - t0))

    for hit in response:
        result = hit.to_dict()

        try:
            for fragment in hit.meta.highlight.title:
                title = clean_fragment_html(fragment)
        except AttributeError:
            title = clean_fragment_html(result["title"])
        texts = []
        try:
            for fragment in hit.meta.highlight.text:
                texts.append(massage_fragment(fragment))
        except AttributeError:
            texts.append(strip_tags(result["text"])[:100] + "...")
        summary = "<br>".join(texts)
        documents.append(
            {
                "url": reverse("blog_post", args=(result["oid"],)),
                "title": title,
                "date": result["pub_date"],
                "summary": summary,
                "score": hit._score,
                "comment": False,
            }
        )

    context["count_documents"] = response.hits.total

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
    search_times.append(("blogcomments", t1 - t0))

    context["count_documents"] += response.hits.total

    if not original_q and not context["count_documents"] and " " in q:
        # recurse
        return search(request, original_q=q)

    blogitem_lookups = set()
    for hit in response:
        result = hit.to_dict()
        texts = []
        try:
            for fragment in hit.meta.highlight.comment:
                texts.append(massage_fragment(fragment))
        except AttributeError:
            texts.append(strip_tags(result["comment"])[:100] + "...")
        summary = "<br>".join(texts)
        blogitem_lookups.add(result["blogitem_id"])
        documents.append(
            {
                "_id": result["blogitem_id"],
                "url": None,
                "title": None,
                "date": result["add_date"],
                "summary": summary,
                "score": hit._score,
                "comment": True,
                "oid": result["oid"],
            }
        )

    if blogitem_lookups:
        blogitems = {}
        blogitem_qs = BlogItem.objects.filter(id__in=blogitem_lookups)
        for blog_item in blogitem_qs.only("title", "oid"):
            blog_item_url = reverse("blog_post", args=(blog_item.oid,))
            blogitems[blog_item.id] = {
                "title": (
                    "Comment on <i>{}</i>".format(clean_fragment_html(blog_item.title))
                ),
                "url": blog_item_url,
            }
        for doc in documents:
            _id = doc.pop("_id", None)
            if _id:
                doc["url"] = blogitems[_id]["url"]
                doc["title"] = blogitems[_id]["title"]
                if doc["comment"]:
                    doc["url"] += "#{}".format(doc["oid"])

    context["documents"] = documents
    context["count_documents_shown"] = len(documents)

    context["search_time"] = sum(x[1] for x in search_times)
    if not context["q"]:
        page_title = "Search"
    elif context["count_documents"] == 1:
        page_title = "1 thing found"
    elif context["count_documents"] == 0:
        page_title = "Nothing found"
    else:
        page_title = "%s things found" % context["count_documents"]
    if context["count_documents_shown"] < context["count_documents"]:
        if context["count_documents_shown"] == 1:
            page_title += " (1 shown)"
        else:
            page_title += " ({} shown)".format(context["count_documents_shown"])
    context["page_title"] = page_title
    context["original_q"] = original_q
    if original_q:
        context["non_stopwords_q"] = [
            x for x in q.split() if x.lower() not in STOPWORDS
        ]

    context["debug_search"] = "debug-search" in request.GET

    print(
        "Searched For",
        request.build_absolute_uri() + "&debug-search=1",
        "and found",
        context["count_documents"],
        "documents",
        "Took",
        "{:.1f}ms".format(context["search_time"] * 1000),
    )
    if not context["debug_search"] and (
        context["q"] or keyword_search or context["original_q"]
    ):
        SearchResult.objects.create(
            q=context["q"],
            original_q=context["original_q"],
            documents_found=context["count_documents"],
            search_time=datetime.timedelta(seconds=context["search_time"]),
            search_times=search_times,
            search_terms=[[str(a), b] for a, b in search_terms],
            keywords=keyword_search,
        )

    return render(request, "homepage/search.html", context)


def autocompete(request):
    q = request.GET.get("q", "")
    if not q:
        return http.JsonResponse({"error": "Missing 'q'"}, status=400)
    size = int(request.GET.get("n", 10))
    terms = [q]
    search_query = BlogItemDoc.search()
    if len(q) > 2:
        suggestion = search_query.suggest("suggestions", q, term={"field": "title"})
        response = suggestion.execute()
        suggestions = response.suggest.suggestions
        for suggestion in suggestions:
            for option in suggestion.options:
                terms.append(q.replace(suggestion.text, option.text))

    search_query.update_from_dict({"query": {"range": {"pub_date": {"lt": "now"}}}})
    query = Q("match_phrase", title_autocomplete=terms[0])
    for term in terms[1:]:
        query |= Q("match_phrase", title_autocomplete=term)

    search_query = search_query.query(query)
    search_query = search_query.sort("-pub_date", "_score")
    search_query = search_query[:size]
    response = search_query.execute()
    results = []
    for hit in response.hits:
        # print('\t', hit.oid, hit.pub_date, hit._score)
        results.append([reverse("blog_post", args=(hit.oid,)), hit.title])

    response = http.JsonResponse({"results": results, "terms": terms})
    return response


@cache_control(public=True, max_age=ONE_WEEK)
def about(request):
    context = {"page_title": "About this site"}
    return render(request, "homepage/about.html", context)


@cache_control(public=True, max_age=ONE_WEEK)
def contact(request):
    context = {"page_title": "Contact me"}
    return render(request, "homepage/contact.html", context)


@cache_control(public=True, max_age=ONE_WEEK)
def sitemap(request):
    base_url = "https://%s" % RequestSite(request).domain

    urls = []
    urls.append('<?xml version="1.0" encoding="iso-8859-1"?>')
    urls.append('<urlset xmlns="http://www.google.com/schemas/sitemap/0.84">')

    def add(loc, lastmod=None, changefreq="monthly", priority=None):
        url = "<url><loc>%s%s</loc>" % (base_url, loc)
        if lastmod:
            url += "<lastmod>%s</lastmod>" % lastmod.strftime("%Y-%m-%d")
        if priority:
            url += "<priority>%s</priority>" % priority
        if changefreq:
            url += "<changefreq>%s</changefreq>" % changefreq
        url += "</url>"
        urls.append(url)

    now = utc_now()
    latest_blogitem, = BlogItem.objects.filter(pub_date__lt=now).order_by("-pub_date")[
        :1
    ]
    add("/", priority=1.0, changefreq="daily", lastmod=latest_blogitem.pub_date)
    add(reverse("about"), changefreq="weekly", priority=0.5)
    add(reverse("contact"), changefreq="weekly", priority=0.5)

    # TODO: Instead of looping over BlogItem, loop over
    # BlogItemTotalHits and use the join to build this list.
    # Then we can sort by a scoring function.
    # This will only work once ALL blogitems have at least 1 hit.
    blogitems = BlogItem.objects.filter(pub_date__lt=now)
    for blogitem in blogitems.order_by("-pub_date"):
        if not blogitem.modify_date:
            # legacy!
            try:
                latest_comment, = BlogComment.objects.filter(
                    approved=True, blogitem=blogitem
                ).order_by("-add_date")[:1]
                blogitem.modify_date = latest_comment.add_date
            except ValueError:
                blogitem.modify_date = blogitem.pub_date
            blogitem._modify_date_set = True
            blogitem.save()

        age = (now - blogitem.modify_date).days
        if age < 14:
            changefreq = "daily"
        elif age < 60:
            changefreq = "weekly"
        elif age < 100:
            changefreq = "monthly"
        else:
            changefreq = None
        add(
            reverse("blog_post", args=[blogitem.oid]),
            lastmod=blogitem.modify_date,
            changefreq=changefreq,
        )

    urls.append("</urlset>")
    return http.HttpResponse("\n".join(urls), content_type="text/xml")


def blog_post_by_alias(request, alias):
    if alias.startswith("static/"):
        # This only really happens when there's no Nginx at play.
        # For example, when the mincss post process thing runs, it's
        # forced to download the 'localhost:8000/static/main.©e9fc100fa.css'
        # file.
        return static.serve(
            request, alias.replace("static/", ""), document_root=settings.STATIC_ROOT
        )
    if alias.startswith("q/") and alias.count("/") == 1:
        # E.g. www.peterbe.com/q/have%20to%20learn
        url = "https://songsear.ch/" + alias
        return http.HttpResponsePermanentRedirect(url)

    lower_endings = (".asp", ".aspx", ".xml", ".php", ".jpg/view")
    if any(alias.lower().endswith(x) for x in lower_endings):
        return http.HttpResponse("Not found", status=404)
    if alias == "...":
        return redirect("/")
    if alias.startswith("podcasttime/podcasts/"):
        return redirect(
            "https://podcasttime.io/{}".format(alias.replace("podcasttime/", ""))
        )
    if alias.startswith("cdn-2916.kxcdn.com/"):
        return redirect("https://" + alias)
    try:
        blogitem = BlogItem.objects.get(alias__iexact=alias)
        url = reverse("blog_post", args=[blogitem.oid])
        return http.HttpResponsePermanentRedirect(url)
    except BlogItem.DoesNotExist:
        print("UNDEALTH WITH ALIAS:", repr(alias))
        # Use http.HttpResponse(..., status=404) if you don't want to wake up
        # Rollbar. Or configure Rollbar to not trigger on Http404 exceptions.
        # return http.HttpResponse(alias, status=404)
        raise http.Http404(alias)


@cache_page(ONE_MONTH)
def humans_txt(request):
    return render(request, "homepage/humans.txt", content_type="text/plain")


def signin(request):
    return render(request, "homepage/signin.html", {"page_title": "Sign In"})


@require_POST
def signout(request):
    logout(request)
    url = "https://" + settings.AUTH0_DOMAIN + "/v2/logout"
    url += "?" + urlencode({"returnTo": settings.AUTH_SIGNOUT_URL})
    return redirect(url)


def huey_test(request):
    a = int(request.GET.get("a", 1))
    b = int(request.GET.get("b", 2))
    crash = request.GET.get("crash")
    wait = request.GET.get("wait")
    sleep = float(request.GET.get("sleep", 0.2))
    task_function = sample_huey_task
    if request.GET.get("orm"):
        task_function = sample_huey_task_with_orm
    if settings.HUEY.get("store_results"):
        queued = task_function(a, b, crash=crash, sleep=sleep)
        result = queued()
        # print("Result:", repr(result))
        for i in range(10):
            time.sleep(0.1 * (i + 1))
            result = queued()
            # print(i, "\tResult:", repr(result))
            if result is not None:
                return http.HttpResponse(str(result))
    elif wait:
        fp = "/tmp/huey.result.{}".format(time.time())
        try:
            task_function(a, b, crash=crash, output_filepath=fp, sleep=sleep)
            slept = 0
            for i in range(10):
                sleep = 0.1 * (i + 1)
                # print("SLEEP", sleep)
                time.sleep(sleep)
                slept += sleep
                try:
                    with open(fp) as f:
                        result = f.read()
                except FileNotFoundError:
                    continue
                return http.HttpResponse("{} after {}s".format(result, slept))
        finally:
            if os.path.isfile(fp):
                os.remove(fp)
    else:
        task_function(a, b, crash=crash, sleep=sleep)

    return http.HttpResponse("OK")


class HueySampleError(Exception):
    """Only for testing."""


@task()
def sample_huey_task(a, b, crash=None, output_filepath=None, sleep=0):
    if sleep:
        time.sleep(sleep)
    if crash:
        raise HueySampleError(crash)
    result = a * b
    if output_filepath:
        with open(output_filepath, "w") as f:
            f.write("{}".format(result))
    else:
        return result


@task()
def sample_huey_task_with_orm(a, b, crash=None, output_filepath=None, sleep=0):
    if sleep:
        time.sleep(sleep)
    if crash:
        raise HueySampleError(crash)
    result = BlogComment.objects.all().count()
    if output_filepath:
        with open(output_filepath, "w") as f:
            f.write("{}".format(result))
    else:
        return result


def slow_static(request, path):
    """Return a static asset but do it slowly. This makes it possible to pretend
    that all other assets, except one or two, is being really slow to serve.

    To use this, you might want to use Nginx. E.g. a config like this:

        location = /static/css/lyrics.min.65f02713ff34.css {
             rewrite (.*) /slowstatic$1;
             proxy_http_version 1.1;
             proxy_set_header Host $http_host;
             proxy_pass http://127.0.0.1:8000;
             break;
       }

    """
    if not path.startswith("static/"):
        return http.HttpResponseBadRequest("Doesn't start with static/")
    p = Path(settings.STATIC_ROOT) / Path(path.replace("static/", ""))
    if not p.is_file():
        return http.HttpResponseNotFound(path)
    time.sleep(2)
    return http.HttpResponse(p.read_bytes(), content_type="text/css")
