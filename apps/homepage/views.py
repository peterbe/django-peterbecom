import time
from pprint import pprint
from cgi import escape as html_escape
import logging
import re
import datetime
from django.shortcuts import render
from django.contrib.sites.models import RequestSite
from apps.plog.models import Category, BlogItem, BlogComment
from apps.plog.utils import render_comment_text

def home(request):
    data = {}
    data['blogitems'] =  (
      BlogItem.objects
      .filter(pub_date__lt=datetime.datetime.utcnow())
      .order_by('-pub_date')
    )[:10]

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

    if len(search) > 1:
        data['q'] = search
        words = re.findall('\w+', search)
        search_escaped = ' & '.join(words)
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
                _sql = ("to_tsvector('english'," + field + ") "
                        "@@ plainto_tsquery('english', %s)")
                items = (qs
                         .extra(where=[_sql], params=[search]))
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

    return render(request, 'homepage/search.html', data)
