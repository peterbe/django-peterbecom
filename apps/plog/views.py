import logging
import datetime
import re
import functools
import json
from collections import defaultdict
from pprint import pprint
from django import http
from django.core.cache import cache
from django.db import transaction
from django.shortcuts import render, get_object_or_404
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from .models import BlogItem, BlogComment, Category
from .utils import render_comment_text
from redisutils import get_redis_connection
from . import tasks


ONE_HOUR = 60 * 60
ONE_DAY = ONE_HOUR * 24


def json_view(f):
    @functools.wraps(f)
    def wrapper(*args, **kw):
        response = f(*args, **kw)
        if isinstance(response, http.HttpResponse):
            return response
        else:
            return http.HttpResponse(json.dumps(response),
                                     content_type='application/json')
    return wrapper


def blog_post(request, oid):
    if oid.endswith('/'):
        oid = oid[:-1]
    try:
        post = BlogItem.objects.get(oid=oid)
    except BlogItem.DoesNotExist:
        try:
            post = BlogItem.objects.get(oid__iexact=oid)
        except BlogItem.DoesNotExist:
            raise http.Http404(oid)

    data = {
      'post': post,
    }
    data['previous_post'] = post.get_previous_by_pub_date()
    data['next_post'] = post.get_next_by_pub_date()
    data['related'] = get_related_posts(post)
    post.save()
    return render(request, 'plog/post.html', data)


def get_related_posts(post):
    cache_key = 'related_ids:%s' % post.pk
    related_pks = cache.get(cache_key)
    if related_pks is None:
        related_pks = _get_related_pks(post, 10)
        cache.set(cache_key, related_pks, ONE_DAY)

    _posts = {}  # cache of posts
    for post in BlogItem.objects.filter(pk__in=related_pks):
        # so we only need 1 query to fetch 10 items in the particular order
        _posts[post.pk] = post
    related = []
    for pk in related_pks:
        related.append(_posts[pk])
    return related


def _get_related_pks(post, max_):
    redis = get_redis_connection()
    count_keywords = redis.get('kwcount')
    if not count_keywords:
        for p in (BlogItem.objects
                  .filter(pub_date__lt=datetime.datetime.utcnow())):
            for keyword in p.keywords:
                redis.sadd('kw:%s' % keyword, p.pk)
                redis.incr('kwcount')

    _keywords = post.keywords
    _related = defaultdict(int)
    for i, keyword in enumerate(_keywords):
        ids = redis.smembers('kw:%s' % keyword)
        for pk in ids:
            pk = int(pk)
            if pk != post.pk:
                _related[pk] += (len(_keywords) - i)
    items = sorted(((v, k) for (k, v) in _related.items()), reverse=True)
    return [y for (x, y) in items][:max_]


def _render_comments(parent):
    raise DeprecatedError('not used anymore')
    html = []
    if parent.__class__ == BlogItem:
        filter_ = {'blogitem': parent, 'parent': None}
    else:
        filter_ = {'parent': parent}
    print (BlogComment.objects
                    .filter(**filter_)
                    .exclude(approved=False)
                    .order_by('add_date')).query
    for comment in (BlogComment.objects
                    .filter(**filter_)
                    .exclude(approved=False)
                    .order_by('add_date')):
        if comment.blogitem is None:
            # legacy problem
            logging.info("correct missing blogitem parent for comment %r" % comment.oid)
            comment.correct_blogitem_parent()
        html.append(_render_comment(comment))
        html.extend(_render_comments(comment))
    return html

def _render_comment(comment):
    return render_to_string('plog/comment.html', {'comment': comment})


@json_view
def prepare_json(request):
    data = {
      'csrf_token': request.META["CSRF_COOKIE"],
      'name': request.COOKIES.get('name',
        request.COOKIES.get('__blogcomment_name')),
      'email': request.COOKIES.get('email',
        request.COOKIES.get('__blogcomment_email')),
    }
    return data


@require_POST
@json_view
def preview_json(request):
    comment = request.POST.get('comment', u'').strip()
    name = request.POST.get('name', u'').strip()
    email = request.POST.get('email', u'').strip()
    if not comment:
        return {}

    html = render_comment_text(comment.strip())
    comment = {
      'oid': 'preview-oid',
      'name': name,
      'email': email,
      'rendered': html,
      'add_date': datetime.datetime.utcnow(),
      }
    html = render_to_string('plog/comment.html', {
      'comment': comment,
      'preview': True,
    })
    return {'html': html}


# Not using @json_view so I can use response.set_cookie first
@require_POST
@transaction.commit_on_success
def submit_json(request, oid):
    post = get_object_or_404(BlogItem, oid=oid)
    comment = request.POST['comment'].strip()
    if not comment:
        return http.HttpResponseBadRequest("Missing comment")
    name = request.POST.get('name', u'').strip()
    email = request.POST.get('email', u'').strip()
    parent = request.POST.get('parent')
    if parent:
        parent = get_object_or_404(BlogComment, oid=parent)
    else:
        parent = None  # in case it was u''

    search = {'comment': comment}
    if name:
        search['name'] = name
    if email:
        search['email'] = email
    if parent:
        search['parent'] = parent

    for comment in BlogComment.objects.filter(**search):
        break
    else:
        comment = BlogComment.objects.create(
          oid=BlogComment.next_oid(),
          blogitem=post,
          parent=parent,
          approved=False,
          comment=comment,
          name=name,
          email=email,
          ip_address=request.META.get('REMOTE_ADDR'),
          user_agent=request.META.get('HTTP_USER_AGENT')
        )
        tasks.akismet_rate.delay(comment.pk)
    html = render_to_string('plog/comment.html', {
      'comment': comment,
      'preview': False,
    })
    data = {'html': html, 'parent': parent and parent.oid or None}
    response = http.HttpResponse(json.dumps(data), mimetype="application/json")
    if name:
        response.set_cookie('name', name)
    if email:
        response.set_cookie('email', email)
    return response
