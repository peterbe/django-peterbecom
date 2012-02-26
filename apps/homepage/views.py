import re
import time
from collections import defaultdict
from pprint import pprint
from cgi import escape as html_escape
import logging
import re
import datetime
import urllib
from django import http
from django.conf import settings
from django.views.decorators.cache import cache_page
from django.shortcuts import render, get_object_or_404
from django.core.urlresolvers import reverse
from django.contrib.sites.models import RequestSite
from apps.plog.models import Category, BlogItem, BlogComment
from apps.plog.utils import render_comment_text
from redisutils import get_redis_connection
from .utils import parse_ocs_to_categories, make_categories_q, split_search


from isodate import UTC
def utc_now():
    """Return a timezone aware datetime instance in UTC timezone

    This funciton is mainly for convenience. Compare:

        >>> from datetimeutil import utc_now
        >>> utc_now()
        datetime.datetime(2012, 1, 5, 16, 42, 13, 639834,
          tzinfo=<isodate.tzinfo.Utc object at 0x101475210>)

    Versus:

        >>> import datetime
        >>> from datetimeutil import UTC
        >>> datetime.datetime.now(UTC)
        datetime.datetime(2012, 1, 5, 16, 42, 13, 639834,
          tzinfo=<isodate.tzinfo.Utc object at 0x101475210>)

    """
    return datetime.datetime.now(UTC)


def _home_key_prefixer(*args, **kwargs):
    print "ARGS", args
    print "KWARGS", kwargs
    return None

#@cache_page(60 * 60, key_prefix=_home_key_prefixer)
def home(request, oc=None):
    data = {}
    qs = BlogItem.objects.filter(pub_date__lt=datetime.datetime.utcnow())
    if oc:
        categories = parse_ocs_to_categories(oc)
        cat_q = make_categories_q(categories)
        qs = qs.filter(cat_q)
        data['categories'] = categories

    BATCH_SIZE = 10
    page = max(1, int(request.GET.get('page', 1))) - 1
    n, m = page * BATCH_SIZE, (page + 1) * BATCH_SIZE
    max_count = qs.count()
    if (page + 1) * BATCH_SIZE < max_count:
        data['next_page'] = page + 2
    data['previous_page'] = page
    data['blogitems'] =  (
      qs
      .prefetch_related('categories')
      .order_by('-pub_date')
    )[n:m]

    return render(request, 'homepage/home.html', data)


STOPWORDS = "a able about across after all almost also am among an and "\
            "any are as at be because been but by can cannot could dear "\
            "did do does either else ever every for from get got had has "\
            "have he her hers him his how however i if in into is it its "\
            "just least let like likely may me might most must my "\
            "neither no nor not of off often on only or other our own "\
            "rather said say says she should since so some than that the "\
            "their them then there these they this tis to too twas us "\
            "wants was we were what when where which while who whom why "\
            "will with would yet you your"

def search(request):
    data = {}
    search = request.GET.get('q', '')
    documents = []
    data['base_url'] = 'http://%s' % RequestSite(request).domain
    tag_strip = re.compile('<[^>]+>')

    def append_match(item, words):

        text = item.rendered
        text = tag_strip.sub(' ', text)

        sentences = []

        def matcher(match):
            return '<b>%s</b>' % match.group()

        if regex:
            for each in regex.finditer(text):
                sentence = text[max(each.start() - 35, 0): each.end() + 40]
                sentence = regex_ext.sub(matcher, sentence)
                sentence = sentence.strip()
                if each.start() > 0 and not sentence[0].isupper():
                    sentence = '...%s' % sentence
                if each.end() < len(text):
                    sentence = '%s...' % sentence
                sentences.append(sentence.strip())
                if len(sentences) > 3:
                    break

        if isinstance(item, BlogItem):
            title = html_escape(item.title)
            if regex_ext:
                title = regex_ext.sub(matcher, title)
            date = item.pub_date
            type_ = 'blog'
        else:
            if not item.blogitem:
                item.correct_blogitem_parent()
            title = ("Comment on <em>%s</em>" %
                     html_escape(item.blogitem.title))
            date = item.add_date
            type_ = 'comment'

        documents.append({
              'title': title,
              'summary': '<br>'.join(sentences),
              'date': date,
              'url': item.get_absolute_url(),
              'type': type_,
            })

    def create_search(s):
        words = re.findall('\w+', s)
        words_orig = words[:]

        if 'or' in words:
            which = words.index('or')
            words_orig.remove('or')
            if (which + 1) < len(words) and which > 0:
                before = words.pop(which - 1)
                words.pop(which - 1)
                after = words.pop(which - 1)
                words.insert(which - 1, '%s | %s' % (before, after))
        while 'and' in words_orig:
            words_orig.remove('and')
        while 'and' in words:
            words.remove('and')

        escaped = ' & '.join(words)
        return escaped, words_orig

    data['q'] = search

    keyword_search = {}
    if len(search) > 1:
        _keyword_keys = ('keyword', 'keywords', 'category', 'categories')
        search, keyword_search = split_search(search, _keyword_keys)
    redis = get_redis_connection()

    not_ids = defaultdict(set)
    times = []
    count_documents = []
    regex = regex_ext = None

    def append_queryset_search(queryset, order_by, words, model_name):
        count = items.count()
        count_documents.append(count)
        for item in items.order_by(order_by)[:20]:
            append_match(item, words)
            not_ids[model_name].add(item.pk)
        return count

    if len(search) > 1:
        search_escaped, words = create_search(search)
        regex = re.compile(r'\b(%s)' % '|'.join(re.escape(word)
                           for word in words
                           if word.lower() not in STOPWORDS),
                           re.I | re.U)
        regex_ext = re.compile(r'\b(%s\w*)\b' % '|'.join(re.escape(word)
                           for word in words
                           if word.lower() not in STOPWORDS),
                           re.I | re.U)

        for model in (BlogItem, BlogComment):
            qs = model.objects
            model_name = model._meta.object_name
            if model == BlogItem:
                fields = ('title', 'text')
                order_by = '-pub_date'
                if keyword_search.get('keyword'):
                    # use Redis!
                    ids = redis.smembers('kw:%s' % keyword_search['keyword'])
                    if ids:
                        qs = qs.filter(pk__in=ids)
                if keyword_search.get('keywords'):
                    # use Redis!
                    ids = []
                    for each in [x.strip() for x
                                 in keyword_search['keywords'].split(',')
                                 if x.strip()]:
                        ids.extend(redis.smembers('kw:%s' % each))
                    if ids:
                        qs = qs.filter(pk__in=ids)
            elif model == BlogComment:
                fields = ('comment',)
                order_by = '-add_date'
                if any(keyword_search.get(k) for k in ('keyword', 'keywords', 'category', 'categories')):
                    # BlogComments don't have this keyword so it can never match
                    continue

            for field in fields:
                if not_ids[model_name]:
                    qs = qs.exclude(pk__in=not_ids[model_name])
                _sql = "to_tsvector('english'," + field + ") "
                if ' | ' in search_escaped or ' & ' in search_escaped:
                    _sql += "@@ to_tsquery('english', %s)"
                else:
                    _sql += "@@ plainto_tsquery('english', %s)"
                items = (qs
                         .extra(where=[_sql], params=[search_escaped]))

                t0 = time.time()
                count = append_queryset_search(items, order_by, words, model_name)
                t1 = time.time()
                times.append('%s to find %s %ss by field %s' % (
                  t1 - t0,
                  count,
                  model_name,
                  field
                ))

        #print 'Searchin for %r:\n%s' % (search, '\n'.join(times))
        logging.info('Searchin for %r:\n%s' % (search, '\n'.join(times)))
    elif keyword_search and any(keyword_search.values()):
        if keyword_search.get('keyword') or keyword_search.get('keywords'):
            if keyword_search.get('keyword'):
                ids = redis.smembers('kw:%s' % keyword_search['keyword'])
            else:
                ids = []
                for each in [x.strip() for x
                             in keyword_search.get('keywords').split(',')
                             if x.strip()]:
                    ids.extend(redis.smembers('kw:%s' % each))
            if ids:
                items = BlogItem.objects.filter(pk__in=ids)
                model_name = BlogItem._meta.object_name
                append_queryset_search(items, '-pub_date', [], model_name)

        if keyword_search.get('category') or keyword_search.get('categories'):
            if keyword_search.get('category'):
                categories = Category.objects.filter(name=keyword_search.get('category'))
            else:
                cats = [x.strip() for x
                        in keyword_search.get('categories').split(',')
                        if x.strip()]
                categories = Category.objects.filter(name__in=cats)
            if categories:
                cat_q = make_categories_q(categories)
                items = BlogItem.objects.filter(cat_q)
                model_name = BlogItem._meta.object_name
                append_queryset_search(items, '-pub_date', [], model_name)

    count_documents_shown = len(documents)
    data['documents'] = documents
    data['count_documents'] = sum(count_documents)
    data['count_documents_shown'] = count_documents_shown
    data['better'] = None
    if not data['count_documents']:
        if ' or ' not in data['q'] and len(data['q'].split()) > 1:
            data['better'] = data['q'].replace(' ', ' or ')
    if data['better']:
        data['better_url'] = reverse('search') + '?' + urllib.urlencode({'q': data['better']})

    if data['count_documents'] == 1:
        page_title = '1 thing found'
    else:
        page_title = '%s things found' % data['count_documents']
    if count_documents_shown < data['count_documents']:
        if count_documents_shown == 1:
            page_title += ' (but only 1 thing shown)'
        else:
            page_title += ' (but only %s things shown)' % count_documents_shown
    data['page_title'] = page_title

    return render(request, 'homepage/search.html', data)


@cache_page(60 * 60 * 1)
def about(request):
    return render(request, 'homepage/about.html')


@cache_page(60 * 60 * 24)
def contact(request):
    return render(request, 'homepage/contact.html')


@cache_page(60 * 60 * 24)
def sitemap(request):
    base_url = 'http://%s' % RequestSite(request).domain

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
    latest_blogitem, = (BlogItem.objects
                        .filter(pub_date__lt=now)
                        .order_by('-pub_date')[:1])
    add('/', priority=1.0, changefreq='daily', lastmod=latest_blogitem.pub_date)
    add(reverse('about'), changefreq='weekly', priority=0.5)
    add(reverse('contact'), changefreq='weekly', priority=0.5)

    for blogitem in (BlogItem.objects
                     .filter(pub_date__lt=now)
                     .order_by('-pub_date')[:1000]):
        if not blogitem.modify_date:
            # legacy!
            try:
                latest_comment, = (BlogComment.objects
                               .filter(approved=True, blogitem=blogitem)
                               .order_by('-add_date')[:1])
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
        add(reverse('blog_post', args=[blogitem.oid]),
            lastmod=blogitem.modify_date,
            changefreq=changefreq
            )

    urls.append('</urlset>')
    return http.HttpResponse('\n'.join(urls), mimetype="text/xml")


def blog_post_by_alias(request, alias):
    blogitem = get_object_or_404(BlogItem, alias=alias)
    url = reverse('blog_post', args=[blogitem.oid])
    return http.HttpResponsePermanentRedirect(url)
