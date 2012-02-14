import re
import time
from pprint import pprint
from cgi import escape as html_escape
import logging
import re
import datetime
import urllib
from django import http
from django.conf import settings
from django.db.models import Q
from django.views.decorators.cache import cache_page
from django.shortcuts import render
from django.core.urlresolvers import reverse
from django.contrib.sites.models import RequestSite
from apps.plog.models import Category, BlogItem, BlogComment
from apps.plog.utils import render_comment_text

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


def home(request, oc=None):
    data = {}
    qs = BlogItem.objects.filter(pub_date__lt=datetime.datetime.utcnow())
    if oc:
        ocs = [x.strip().replace('+',' ') for x
               in re.split('/oc-(.*?)', oc) if x.strip()]
        categories = Category.objects.filter(name__in=ocs)
        if len(categories) != len(ocs):
            raise http.Http404("Unrecognized categories")
        cat_q = None
        for category in categories:
            if cat_q is None:
                cat_q = Q(categories=category)
            else:
                cat_q = cat_q | Q(categories=category)
        qs = qs.filter(cat_q)
        data['categories'] = categories

    BATCH_SIZE = 10
    page = max(1, int(request.GET.get('page', 1))) - 1
    n, m = page * BATCH_SIZE, (page + 1) * BATCH_SIZE
    #print page
    #print (n,m)
    max_count = qs.count()
    #print "max_count", max_count
    if (page + 1) * BATCH_SIZE < max_count:
        data['next_page'] = page + 2
    data['previous_page'] = page
    data['blogitems'] =  (
      qs
      .prefetch_related('categories')
      .order_by('-pub_date')
    )[n:m]

    return render(request, 'homepage/home.html', data)


def search(request):
    data = {}
    search = request.GET.get('q', '')
    documents = []
    data['base_url'] = 'http://%s' % RequestSite(request).domain
    tag_strip = re.compile('<[^>]+>')

    def append(item, words):

        text = item.rendered
        text = tag_strip.sub(' ', text)

        sentences = []
        def matcher(match):
            return '<b>%s</b>' % match.group()
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

    if len(search) > 1:
        data['q'] = search
        search_escaped, words = create_search(search)
        regex = re.compile(r'\b(%s)' % '|'.join(re.escape(word) for word in words),
                           re.I | re.U)
        regex_ext = re.compile(r'\b(%s\w*)\b' % '|'.join(re.escape(word) for word in words),
                           re.I | re.U)

        not_ids = set()
        times = []
        count_documents = 0
        for model in (BlogItem, BlogComment):
            if model == BlogItem:
                fields = ('title', 'text')
                order_by = '-pub_date'
            elif model == BlogComment:
                fields = ('comment',)
                order_by = '-add_date'

            qs = model.objects
            for field in fields:
                if not_ids:
                    qs = qs.exclude(pk__in=not_ids)
                _sql = "to_tsvector('english'," + field + ") "
                if ' | ' in search_escaped or ' & ' in search_escaped:
                    _sql += "@@ to_tsquery('english', %s)"
                else:
                    _sql += "@@ plainto_tsquery('english', %s)"
                items = (qs
                         .extra(where=[_sql], params=[search_escaped]))
                count = items.count()
                count_documents += count
                t0 = time.time()
                for item in items.order_by(order_by)[:20]:
                    append(item, words)
                    not_ids.add(item.pk)
                t1 = time.time()
                times.append('%s to find %s %ss by field %s' % (
                  t1 - t0,
                  count,
                  model.__name__,
                  field
                ))
        #print 'Searchin for %r:\n%s' % (search, '\n'.join(times))
        logging.info('Searchin for %r:\n%s' % (search, '\n'.join(times)))

    data['documents'] = documents
    data['count_documents'] = count_documents
    data['count_documents_shown'] = len(documents)
    data['better'] = None
    if not count_documents:
        if ' or ' not in data['q'] and len(data['q'].split()) > 1:
            data['better'] = data['q'].replace(' ', ' or ')
    if data['better']:
        data['better_url'] = reverse('search') + '?' + urllib.urlencode({'q': data['better']})

    return render(request, 'homepage/search.html', data)


#@cache_page(60 * 60 * int(settings.DEBUG))
def about(request):
    return render(request, 'homepage/about.html')


@cache_page(60 * 60 * int(settings.DEBUG))
def contact(request):
    return render(request, 'homepage/contact.html')


@cache_page(60 * 60 * 24 * int(settings.DEBUG))
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
