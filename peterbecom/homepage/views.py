import re
import os
import tempfile
import time
import logging
import urllib

from elasticsearch_dsl import Q

from django import http
from django.core.cache import cache
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.core.urlresolvers import reverse
from django.contrib.sites.requests import RequestSite
from django.views.decorators.cache import cache_control
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.utils.html import strip_tags

from peterbecom.plog.models import BlogItem, BlogComment
from peterbecom.plog.utils import utc_now
from .utils import (
    parse_ocs_to_categories,
    make_categories_q,
    split_search,
    STOPWORDS
)
from fancy_cache import cache_page
from peterbecom.plog.utils import make_prefix
from peterbecom.plog.search import BlogItemDoc, BlogCommentDoc
from .tasks import sample_task


logger = logging.getLogger('homepage')


ONE_HOUR = 60 * 60
ONE_DAY = ONE_HOUR * 24
ONE_WEEK = ONE_DAY * 7
ONE_MONTH = ONE_WEEK * 4


def _home_key_prefixer(request):
    if request.method != 'GET':
        return None
    prefix = make_prefix(request.GET)
    cache_key = 'latest_comment_add_date'
    if request.path_info.startswith('/oc-'):
        categories = parse_ocs_to_categories(request.path_info[len('/oc-'):])
        cache_key += ''.join(str(x.pk) for x in categories)
    else:
        categories = None

    latest_date = cache.get(cache_key)
    if latest_date is None:
        qs = BlogItem.objects.all()
        if categories:
            cat_q = make_categories_q(categories)
            qs = qs.filter(cat_q)
        latest, = qs.order_by('-modify_date').values('modify_date')[:1]
        latest_date = latest['modify_date'].strftime('%f')
        cache.set(cache_key, latest_date, ONE_DAY)
    prefix += str(latest_date)

    return prefix


@cache_control(public=True, max_age=ONE_HOUR * 1)
# @cache_page(
#     ONE_HOUR * 3,
#     key_prefix=_home_key_prefixer,
# )
def home(request, oc=None, page=1):
    context = {}
    qs = BlogItem.objects.filter(pub_date__lt=utc_now())
    if oc is not None:
        if not oc:  # empty string
            return redirect('/', permanent=True)
        categories = parse_ocs_to_categories(oc)
        cat_q = make_categories_q(categories)
        qs = qs.filter(cat_q)
        context['categories'] = categories

    # Reasons for not being here
    if request.method == 'HEAD':
        return http.HttpResponse('')

    BATCH_SIZE = 10
    try:
        page = max(1, int(page)) - 1
    except ValueError:
        raise http.Http404('invalid page value')
    n, m = page * BATCH_SIZE, (page + 1) * BATCH_SIZE
    max_count = qs.count()
    if page * BATCH_SIZE > max_count:
        return http.HttpResponse('Too far back in time\n', status=404)
    if (page + 1) * BATCH_SIZE < max_count:
        context['next_page'] = page + 2
    context['previous_page'] = page

    if context.get('categories'):
        oc_path = '/'.join(
            ['oc-{}'.format(c.name) for c in context['categories']]
        )
        oc_path = oc_path[3:]

    if context.get('next_page'):
        if context.get('categories'):
            next_page_url = reverse(
                'only_category_paged',
                args=(oc_path, context['next_page'])
            )
        else:
            next_page_url = reverse(
                'home_paged',
                args=(context['next_page'],)
            )
        context['next_page_url'] = next_page_url

    if context['previous_page'] > 1:
        if context.get('categories'):
            previous_page_url = reverse(
                'only_category_paged',
                args=(oc_path, context['previous_page'])
            )
        else:
            previous_page_url = reverse(
                'home_paged',
                args=(context['previous_page'],)
            )
        context['previous_page_url'] = previous_page_url
    elif context['previous_page']:  # i.e. == 1
        if context.get('categories'):
            previous_page_url = reverse(
                'only_category',
                args=(oc_path,)
            )
        else:
            previous_page_url = '/'
        context['previous_page_url'] = previous_page_url

    context['blogitems'] = (
        qs
        .prefetch_related('categories')
        .order_by('-pub_date')
    )[n:m]

    if page > 0:  # page starts on 0
        context['page_title'] = 'Page {}'.format(page + 1)

    return render(request, 'homepage/home.html', context)


_uppercase = set('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
_html_regex = re.compile(r'<.*?>')


def htmlify_text(text, newline_to_br=True, allow=()):
    allow_ = []
    for each in allow:
        allow_.append('<{}>'.format(each))
        allow_.append('</{}>'.format(each))

    def replacer(match):
        group = match.group()
        if group in allow_:
            # let it be
            return group
        return ''

    html = _html_regex.sub(replacer, text)
    if newline_to_br:
        html = html.replace('\n', '<br/>')
    return html


def massage_fragment(text, max_length=300):
    while len(text) > max_length:
        split = text.split()
        d_left = text.find('<mark>')
        d_right = len(text) - text.rfind('</mark>')
        if d_left > d_right:
            # there's more non-<mark> on the left
            split = split[1:]
        else:
            split = split[:-1]
        text = ' '.join(split)
    text = text.strip()
    if not text.endswith('.'):
        text += '…'
    text = text.lstrip(', ')
    text = text.lstrip('. ')
    if text[0] not in _uppercase:
        text = '…' + text
    text = htmlify_text(
        text,
        newline_to_br=False,
        allow=('mark',)
    )
    text = text.replace('</mark> <mark>', ' ')
    return text


def clean_fragment_html(fragment):

    def replacer(match):
        group = match.group()
        if group in ('<mark>', '</mark>'):
            return group
        return ''

    fragment = _html_regex.sub(replacer, fragment)
    return fragment.replace('</mark> <mark>', ' ')


def search(request, original_q=None):
    context = {}
    q = request.GET.get('q', '')
    if len(q) > 90:
        return http.HttpResponse("Search too long")

    LIMIT_BLOG_ITEMS = 30
    LIMIT_BLOG_COMMENTS = 20

    documents = []
    search_times = []
    context['base_url'] = 'https://%s' % RequestSite(request).domain

    context['q'] = q

    keyword_search = {}
    if len(q) > 1:
        _keyword_keys = ('keyword', 'keywords', 'category', 'categories')
        q, keyword_search = split_search(q, _keyword_keys)

    search_terms = [(1.1, q)]
    _search_terms = set([q])
    doc_type_keys = (
        (BlogItemDoc, ('title', 'text')),
        (BlogCommentDoc, ('comment',)),
    )
    for doc_type, keys in doc_type_keys:
        suggester = doc_type.search()
        for key in keys:
            suggester = suggester.suggest('sugg', q, term={'field': key})
        suggestions = suggester.execute_suggest()
        for each in suggestions.sugg:
            if each.options:
                for option in each.options:
                    if option.score >= 0.6:
                        better = q.replace(each['text'], option['text'])
                        if better not in _search_terms:
                            search_terms.append((
                                option['score'],
                                better,
                            ))
                            _search_terms.add(better)

    search_query = BlogItemDoc.search()
    search_query.update_from_dict({
        'query': {
            'range': {
                'pub_date': {
                    'lt': 'now'
                }
            }
        }
    })

    if keyword_search.get('keyword'):
        search_query = search_query.filter(
            'terms',
            keywords=[keyword_search['keyword']]
        )
    if keyword_search.get('category'):
        search_query = search_query.filter(
            'terms',
            categories=[keyword_search['category']]
        )

    matcher = None
    search_terms.sort(reverse=True)
    max_search_terms = 5  # to not send too much stuff to ES
    if len(search_terms) > max_search_terms:
        search_terms = search_terms[:max_search_terms]

    strategy = 'match_phrase'
    if original_q:
        strategy = 'match'
    search_term_boosts = {}
    for i, (score, word) in enumerate(search_terms):
        # meaning the first search_term should be boosted most
        j = len(search_terms) - i
        boost = 1 * j * score
        boost_title = 2 * boost
        search_term_boosts[word] = (boost_title, boost)
        match = Q(strategy, title={
            'query': word,
            'boost': boost_title,
        }) | Q(strategy, text={
            'query': word,
            'boost': boost,
        })
        if matcher is None:
            matcher = match
        else:
            matcher |= match

    context['search_terms'] = search_terms
    context['search_term_boosts'] = search_term_boosts

    search_query = search_query.query(matcher)

    search_query = search_query.highlight(
        'text',
        fragment_size=80,
        number_of_fragments=2,
    )
    search_query = search_query.highlight(
        'title',
        fragment_size=120,
        number_of_fragments=1,
    )
    search_query = search_query.highlight_options(
        pre_tags=['<mark>'],
        post_tags=['</mark>'],
    )
    search_query = search_query[:LIMIT_BLOG_ITEMS]
    t0 = time.time()
    response = search_query.execute()
    t1 = time.time()
    search_times.append(t1 - t0)

    for hit in response:
        result = hit.to_dict()

        try:
            for fragment in hit.meta.highlight.title:
                title = clean_fragment_html(fragment)
        except AttributeError:
            title = clean_fragment_html(result['title'])
        texts = []
        try:
            for fragment in hit.meta.highlight.text:
                texts.append(massage_fragment(fragment))
        except AttributeError:
            texts.append(strip_tags(result['text'])[:100] + '...')
        summary = '<br>'.join(texts)
        documents.append({
            'url': reverse('blog_post', args=(result['oid'],)),
            'title': title,
            'date': result['pub_date'],
            'summary': summary,
            'score': hit._score,
        })

    context['count_documents'] = response.hits.total
    if not original_q and not response.hits.total and ' ' in q:
        # recurse
        return search(request, original_q=q)

    # Now append the search results based on blog comments
    search_query = BlogCommentDoc.search()
    search_query = search_query.filter('term', approved=True)
    search_query = search_query.query('match_phrase', comment=q)

    search_query = search_query.highlight(
        'comment',
        fragment_size=80,
        number_of_fragments=2,
    )
    search_query = search_query.highlight_options(
        pre_tags=['<mark>'],
        post_tags=['</mark>'],
    )
    search_query = search_query[:LIMIT_BLOG_COMMENTS]
    t0 = time.time()
    response = search_query.execute()
    t1 = time.time()
    search_times.append(t1 - t0)

    context['count_documents'] += response.hits.total

    blogitem_lookups = set()
    for hit in response:
        result = hit.to_dict()
        texts = []
        try:
            for fragment in hit.meta.highlight.comment:
                texts.append(massage_fragment(fragment))
        except AttributeError:
            texts.append(strip_tags(result['comment'])[:100] + '...')
        summary = '<br>'.join(texts)
        blogitem_lookups.add(result['blogitem_id'])
        documents.append({
            '_id': result['blogitem_id'],
            'url': None,
            'title': None,
            'date': result['add_date'],
            'summary': summary,
            'score': hit._score,
        })

    if blogitem_lookups:
        blogitems = {}
        blogitem_qs = BlogItem.objects.filter(id__in=blogitem_lookups)
        for blog_item in blogitem_qs.only('title', 'oid'):
            blogitems[blog_item.id] = {
                'title': (
                    'Comment on <i>{}</i>'.format(
                        clean_fragment_html(blog_item.title)
                    )
                ),
                'url': reverse('blog_post', args=(blog_item.oid,)),
            }
        for doc in documents:
            _id = doc.pop('_id', None)
            if _id:
                doc['url'] = blogitems[_id]['url']
                doc['title'] = blogitems[_id]['title']

    context['documents'] = documents
    context['count_documents_shown'] = len(documents)

    context['search_time'] = sum(search_times)
    if not context['q']:
        page_title = 'Search'
    elif context['count_documents'] == 1:
        page_title = '1 thing found'
    elif context['count_documents'] == 0:
        page_title = 'Nothing found'
    else:
        page_title = '%s things found' % context['count_documents']
    if context['count_documents_shown'] < context['count_documents']:
        if context['count_documents_shown'] == 1:
            page_title += ' (1 shown)'
        else:
            page_title += ' ({} shown)'.format(
                context['count_documents_shown']
            )
    context['page_title'] = page_title
    context['original_q'] = original_q
    if original_q:
        context['non_stopwords_q'] = [
            x for x in q.split() if x.lower() not in STOPWORDS
        ]

    context['debug_search'] = 'debug-search' in request.GET

    return render(request, 'homepage/search.html', context)


def autocompete(request):
    q = request.GET.get('q', '')
    if not q:
        return http.JsonResponse({'error': "Missing 'q'"}, status=400)
    size = int(request.GET.get('n', 10))
    terms = [q]
    search_query = BlogItemDoc.search()
    if len(q) > 2:
        suggestion = search_query.suggest('suggestions', q, term={
            'field': 'title',
        })
        suggestions = suggestion.execute_suggest()
        for suggestion in getattr(suggestions, 'suggestions', []):
            for option in suggestion.options:
                terms.append(
                    q.replace(suggestion.text, option.text)
                )

    search_query.update_from_dict({
        'query': {
            'range': {
                'pub_date': {
                    'lt': 'now'
                }
            }
        }
    })
    # print('TERMS', terms)
    query = Q('match_phrase', title=terms[0])
    for term in terms[1:]:
        query |= Q('match_phrase', title=term)

    search_query = search_query.query(query)
    search_query = search_query.sort('-pub_date', '_score')
    search_query = search_query[:size]
    response = search_query.execute()
    results = []
    for hit in response.hits:
        # print(hit.pub_date, hit._score)
        results.append([
            reverse('blog_post', args=(hit.oid,)),
            hit.title,
        ])

    response = http.JsonResponse({
        'results': results,
        'terms': terms,
    })
    return response


@cache_control(public=True, max_age=ONE_WEEK)
def about(request):
    context = {
        'page_title': 'About this site',
    }
    return render(request, 'homepage/about.html', context)


@cache_control(public=True, max_age=ONE_WEEK)
def contact(request):
    context = {
        'page_title': 'Contact me',
    }
    return render(request, 'homepage/contact.html', context)


@cache_control(public=True, max_age=ONE_WEEK)
def sitemap(request):
    base_url = 'https://%s' % RequestSite(request).domain

    urls = []
    urls.append('<?xml version="1.0" encoding="iso-8859-1"?>')
    urls.append('<urlset xmlns="http://www.google.com/schemas/sitemap/0.84">')

    def add(loc, lastmod=None, changefreq='monthly', priority=None):
        url = '<url><loc>%s%s</loc>' % (base_url, loc)
        if lastmod:
            url += '<lastmod>%s</lastmod>' % lastmod.strftime('%Y-%m-%d')
        if priority:
            url += '<priority>%s</priority>' % priority
        if changefreq:
            url += '<changefreq>%s</changefreq>' % changefreq
        url += '</url>'
        urls.append(url)

    now = utc_now()
    latest_blogitem, = (
        BlogItem.objects
        .filter(pub_date__lt=now)
        .order_by('-pub_date')[:1]
    )
    add(
        '/',
        priority=1.0,
        changefreq='daily',
        lastmod=latest_blogitem.pub_date
    )
    add(reverse('about'), changefreq='weekly', priority=0.5)
    add(reverse('contact'), changefreq='weekly', priority=0.5)

    # TODO: Instead of looping over BlogItem, loop over
    # BlogItemTotalHits and use the join to build this list.
    # Then we can sort by a scoring function.
    # This will only work once ALL blogitems have at least 1 hit.
    blogitems = BlogItem.objects.filter(
        pub_date__lt=now
    )
    for blogitem in blogitems.order_by('-pub_date'):
        if not blogitem.modify_date:
            # legacy!
            try:
                latest_comment, = (
                    BlogComment.objects
                    .filter(approved=True, blogitem=blogitem)
                    .order_by('-add_date')[:1]
                )
                blogitem.modify_date = latest_comment.add_date
            except ValueError:
                blogitem.modify_date = blogitem.pub_date
            blogitem._modify_date_set = True
            blogitem.save()

        age = (now - blogitem.modify_date).days
        if age < 14:
            changefreq = 'daily'
        elif age < 60:
            changefreq = 'weekly'
        elif age < 100:
            changefreq = 'monthly'
        else:
            changefreq = None
        add(
            reverse('blog_post', args=[blogitem.oid]),
            lastmod=blogitem.modify_date,
            changefreq=changefreq
        )

    urls.append('</urlset>')
    return http.HttpResponse('\n'.join(urls), content_type="text/xml")


def blog_post_by_alias(request, alias):
    if alias.startswith('static/'):
        raise http.Http404('Bad alias for a static URL {!r}'.format(alias))
    blogitem = get_object_or_404(BlogItem, alias=alias)
    url = reverse('blog_post', args=[blogitem.oid])
    return http.HttpResponsePermanentRedirect(url)


@cache_page(ONE_MONTH)
def humans_txt(request):
    return render(
        request,
        'homepage/humans.txt',
        content_type='text/plain'
    )


@login_required
def celerytester(request):
    if request.method == 'POST':
        filepath = os.path.join(tempfile.gettempdir(), 'celerytester.log')
        if os.path.isfile(filepath):
            os.remove(filepath)
        assert sample_task.delay(filepath)
        for i in range(1, 5):
            if os.path.isfile(filepath):
                result = open(filepath).read()
                os.remove(filepath)
                return http.HttpResponse(result)
            time.sleep(i)
        return http.HttpResponse('Did not work :(')
    return render(request, 'homepage/celerytester.html')


def signin(request):
    return render(request, 'homepage/signin.html', {
        'page_title': 'Sign In'
    })


@require_POST
def signout(request):
    logout(request)
    url = 'https://' + settings.AUTH0_DOMAIN + '/v2/logout'
    url += '?' + urllib.urlencode({
        'returnTo': settings.AUTH_SIGNOUT_URL,
    })
    return redirect(url)
