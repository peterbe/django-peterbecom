import urllib
import logging
import datetime
import re
import functools
import json
from collections import defaultdict
from pprint import pprint
from django.contrib.sites.models import Site
from django.core.urlresolvers import reverse
from django.template import Context, loader
from django import http
from django.core.cache import cache
from django.views.decorators.cache import cache_page
from django.db import transaction
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.template import Template
from django.conf import settings
from .models import BlogItem, BlogComment, Category
from .utils import render_comment_text, valid_email, utc_now
from apps.redisutils import get_redis_connection
from apps.view_cache_utils import cache_page_with_prefix
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


def _blog_post_key_prefixer(request):
    if request.method != 'GET':
        return None
    if request.user.is_authenticated():
        return None
    prefix = urllib.urlencode(request.GET)
    oid = request.path.split('/')[-1]
    cache_key = 'latest_comment_add_date:%s' % oid
    latest_date = cache.get(cache_key)
    if latest_date is None:
        try:
            blogitem = BlogItem.objects.get(oid=oid)
        except BlogItem.DoesNotExist:
            # don't bother, something's really wrong
            return None
        latest_date = blogitem.modify_date
        for c in (BlogComment.objects
                  .filter(blogitem=blogitem, add_date__gt=latest_date)
                  .order_by('-add_date')[:1]):
            latest_date = c.add_date
        latest_date = latest_date.strftime('%f')
        cache.set(cache_key, latest_date, ONE_DAY)
    prefix += str(latest_date)
    return prefix


@cache_page_with_prefix(ONE_DAY, _blog_post_key_prefixer)
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
    try:
        data['previous_post'] = post.get_previous_by_pub_date()
    except BlogItem.DoesNotExist:
        data['previous_post'] = None
    try:
        data['next_post'] = post.get_next_by_pub_date(pub_date__lt=utc_now())
    except BlogItem.DoesNotExist:
        data['next_post'] = None
    data['related'] = get_related_posts(post)

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
                  .filter(pub_date__lt=utc_now())):
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
    # http://stackoverflow.com/a/7503362/205832
    request.META['CSRF_COOKIE_USED'] = True
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
      'add_date': utc_now(),
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

    for blog_comment in BlogComment.objects.filter(**search):
        break
    else:
        blog_comment = BlogComment.objects.create(
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
        if not settings.DEBUG:
            tasks.akismet_rate.delay(blog_comment.pk)

        tos = [x[1] for x in settings.ADMINS]
        from_ = ['%s <%s>' % x for x in settings.ADMINS][0]
        body = _get_comment_body(post, blog_comment)
        send_mail("Peterbe.com: New comment on '%s'" % post.title,
                  body, from_, tos)

    html = render_to_string('plog/comment.html', {
      'comment': blog_comment,
      'preview': True,
    })
    data = {'html': html, 'parent': parent and parent.oid or None}
    response = http.HttpResponse(json.dumps(data), mimetype="application/json")
    if name:
        if isinstance(name, unicode):
            name = name.encode('utf-8')
        response.set_cookie('name', name)
    if email:
        response.set_cookie('email', email)
    return response


@login_required
def approve_comment(request, oid, comment_oid):
    blogitem = get_object_or_404(BlogItem, oid=oid)
    blogcomment = get_object_or_404(BlogComment, oid=comment_oid)
    if blogcomment.blogitem != blogitem:
        raise http.Http404("bad rel")

    blogcomment.approved = True
    blogcomment.save()

    if (blogcomment.parent and blogcomment.parent.email
        and valid_email(blogcomment.parent.email)
        and blogcomment.email != blogcomment.parent.email):
        parent = blogcomment.parent
        tos = [parent.email]
        from_ = 'Peterbe.com <noreply+%s@peterbe.com>' % blogcomment.oid
        body = _get_comment_reply_body(blogitem, blogcomment, parent)
        subject = 'Peterbe.com: Reply to your comment'
        send_mail(subject, body, from_, tos)
    if request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
        return http.HttpResponse('OK')
    else:
        url = blogitem.get_absolute_url()
        if blogcomment.blogitem:
            url += '#%s' % blogcomment.blogitem.oid
        return http.HttpResponse('''<html>Comment approved<br>
        <a href="%s">%s</a>
        </html>
        ''' % (url, blogitem.title))


def _get_comment_body(blogitem, blogcomment):
    base_url = 'http://%s' % Site.objects.get(pk=settings.SITE_ID).domain
    approve_url = reverse('approve_comment', args=[blogitem.oid, blogcomment.oid])
    delete_url = reverse('delete_comment', args=[blogitem.oid, blogcomment.oid])
    message = template = loader.get_template('plog/comment_body.txt')
    context = {
      'post': blogitem,
      'comment': blogcomment,
      'approve_url': approve_url,
      'delete_url': delete_url,
      'base_url': base_url,
    }
    return template.render(Context(context)).strip()


def _get_comment_reply_body(blogitem, blogcomment, parent):
    base_url = 'http://%s' % Site.objects.get(pk=settings.SITE_ID).domain
    approve_url = reverse('approve_comment', args=[blogitem.oid, blogcomment.oid])
    delete_url = reverse('delete_comment', args=[blogitem.oid, blogcomment.oid])
    message = template = loader.get_template('plog/comment_reply_body.txt')
    context = {
      'post': blogitem,
      'comment': blogcomment,
      'parent': parent,
      'base_url': base_url,
    }
    return template.render(Context(context)).strip()


@login_required
def delete_comment(request, oid, comment_oid):
    user = request.user
    assert user.is_staff or user.is_superuser
    blogitem = get_object_or_404(BlogItem, oid=oid)
    blogcomment = get_object_or_404(BlogComment, oid=comment_oid)
    if blogcomment.blogitem != blogitem:
        raise http.Http404("bad rel")

    blogcomment.delete()

    return http.HttpResponse("Comment deleted")


@cache_page(60 * 60 * 1)  # might want to up this later
def plog_index(request):
    groups = defaultdict(list)
    now = utc_now()
    group_dates = []

    _categories = dict((x.pk, x.name) for x in
                        Category.objects.all())
    blogitem_categories = defaultdict(list)
    for cat_item in BlogItem.categories.through.objects.all():
        blogitem_categories[cat_item.blogitem_id].append(
          _categories[cat_item.category_id]
        )
    for item in (BlogItem.objects
                 .filter(pub_date__lt=now)
                 .values('pub_date', 'oid', 'title', 'pk')
                 .order_by('-pub_date')):
        group = item['pub_date'].strftime('%Y.%m')
        item['categories'] = blogitem_categories[item['pk']]
        groups[group].append(item)
        tup = (group, item['pub_date'].strftime('%B, %Y'))
        if tup not in group_dates:
            group_dates.append(tup)

    data = {
      'groups': groups,
      'group_dates': group_dates,
    }
    return render(request, 'plog/index.html', data)


def new_comments(request):
    data = {}
    comments = BlogComment.objects.all()
    if request.GET.get('admin'):
        if not request.user.is_authenticated():
            return redirect('/admin/')
    else:
        comments = comments.filter(approved=True)

    # legacy stuff that can be removed in march 2012
    for c in comments.filter(blogitem__isnull=True):
        if not c.parent:
            c.delete()
        else:
            c.correct_blogitem_parent()

    data['comments'] = (comments
                        .order_by('-add_date')
                        .select_related('blogitem')[:100])
    return render(request, 'plog/new-comments.html', data)
