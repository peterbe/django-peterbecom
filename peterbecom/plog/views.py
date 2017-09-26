import hashlib
import logging
import datetime
from collections import defaultdict
from statistics import median

from django.contrib.sites.models import Site
from django.core.urlresolvers import reverse
from django.template import loader
from django import http
from django.core.cache import cache
from django.db import transaction
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.contrib.sites.requests import RequestSite
from django.views.decorators.cache import cache_control
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie

from peterbecom.base.templatetags.jinja_helpers import thumbnail
from .models import (
    BlogItem,
    BlogComment,
    Category,
    BlogFile,
    BlogItemHit,
    OneTimeAuthKey,
)
from .search import BlogItemDoc
from .utils import render_comment_text, valid_email, utc_now
from fancy_cache import cache_page
from . import utils
from .utils import json_view
from .forms import BlogForm, BlogFileUpload, CalendarDataForm
from . import tasks


logger = logging.getLogger('plog.views')


ONE_HOUR = 60 * 60
ONE_DAY = ONE_HOUR * 24
ONE_WEEK = ONE_DAY * 7
ONE_MONTH = ONE_WEEK * 4
ONE_YEAR = ONE_WEEK * 52
THIS_YEAR = timezone.now().year


def _blog_post_key_prefixer(request):
    prefix = getattr(request, '_prefix', None)
    if prefix is not None:
        return prefix
    # print("PREFIXED?", getattr(request, '_prefixed', None))
    if request.method != 'GET':
        return None
    if request.user.is_authenticated():
        return None
    prefix = utils.make_prefix(request.GET)

    # all_comments = False
    if request.path.endswith('/all-comments'):
        oid = request.path.split('/')[-2]
        # all_comments = True
    elif request.path.endswith('/'):
        oid = request.path.split('/')[-2]
    else:
        oid = request.path.split('/')[-1]

    try:
        cache_key = 'latest_comment_add_date:%s' % (
            hashlib.md5(oid.encode('utf-8')).hexdigest()
        )
    except UnicodeEncodeError:
        # If the 'oid' can't be converted to ascii, then it's not likely
        # to be a valid 'oid'.
        return None
    latest_date = cache.get(cache_key)
    if latest_date is None:
        try:
            blogitem = (
                BlogItem.objects.filter(oid=oid)
                .values('pk', 'modify_date')[0]
            )
        except IndexError:
            # don't bother, something's really wrong
            return None
        latest_date = blogitem['modify_date']
        blogitem_pk = blogitem['pk']
        for c in (BlogComment.objects
                  .filter(blogitem=blogitem_pk,
                          add_date__gt=latest_date)
                  .values('add_date')
                  .order_by('-add_date')[:1]):
            latest_date = c['add_date']
        latest_date = latest_date.strftime('%f')
        cache.set(cache_key, latest_date, ONE_MONTH)
    prefix += str(latest_date)

    # if not all_comments:
    #     # temporary solution because I can't get Google Analytics API to work
    #     ua = request.META.get('HTTP_USER_AGENT', '')
    #     if not utils.is_bot(ua):
    #         tasks.increment_blogitem_hit.delay(oid)

    # This is a HACK!
    # This prefixer function gets called, first for the request,
    # then for the response. The answer is not going to be any different.
    request._prefix = prefix
    return prefix


@cache_control(public=True, max_age=ONE_WEEK)
@cache_page(
    ONE_WEEK,
    _blog_post_key_prefixer,
)
def blog_post(request, oid):
    # legacy fix
    if request.GET.get('comments') == 'all':
        if '/all-comments' in request.path:
            return http.HttpResponseBadRequest('invalid URL')
        return redirect(request.path + '/all-comments', permanent=True)

    return _render_blog_post(request, oid)


@require_http_methods(['PUT'])
@csrf_exempt
def blog_post_ping(request, oid):
    if not utils.is_bot(
        ua=request.META.get('HTTP_USER_AGENT', ''),
        ip=request.META.get('REMOTE_ADDR'),
    ):
        http_referer = request.GET.get(
            'referrer',
            request.META.get('HTTP_REFERER')
        )
        if http_referer:
            current_url = request.build_absolute_uri().split('/ping')[0]
            if current_url == http_referer:
                http_referer = None
        tasks.increment_blogitem_hit.delay(
            oid,
            http_user_agent=request.META.get('HTTP_USER_AGENT'),
            http_accept_language=request.META.get('HTTP_ACCEPT_LANGUAGE'),
            remote_addr=request.META.get('REMOTE_ADDR'),
            http_referer=http_referer,
        )
    return http.JsonResponse({'ok': True})


def blog_screenshot(request, oid):
    response = _render_blog_post(request, oid, screenshot_mode=True)
    return response


def _render_blog_post(request, oid, screenshot_mode=False):
    if oid.endswith('/'):
        oid = oid[:-1]
    try:
        post = BlogItem.objects.get(oid=oid)
    except BlogItem.DoesNotExist:
        try:
            post = BlogItem.objects.get(oid__iexact=oid)
        except BlogItem.DoesNotExist:
            if oid == 'add':
                return redirect(reverse('add_post'))
            raise http.Http404(oid)

    # If you try to view a blog post that is beyond one day in the
    # the future it should raise a 404 error.
    future = timezone.now() + datetime.timedelta(days=1)
    if post.pub_date > future:
        raise http.Http404('not published yet')

    # Reasons for not being here
    if request.method == 'HEAD':
        return http.HttpResponse('')
    elif (
        request.method == 'GET' and
        (request.GET.get('replypath') or request.GET.get('show-comments'))
    ):
        return http.HttpResponsePermanentRedirect(request.path)

    # attach a field called `_absolute_url` which depends on the request
    base_url = 'https://' if request.is_secure() else 'http://'
    base_url += RequestSite(request).domain
    post._absolute_url = base_url + reverse('blog_post', args=(post.oid,))

    context = {
        'post': post,
        'screenshot_mode': screenshot_mode,
    }
    try:
        context['previous_post'] = post.get_previous_by_pub_date()
    except BlogItem.DoesNotExist:
        context['previous_post'] = None
    try:
        context['next_post'] = post.get_next_by_pub_date(
            pub_date__lt=utc_now()
        )
    except BlogItem.DoesNotExist:
        context['next_post'] = None

    if post.screenshot_image:
        context['screenshot_image'] = thumbnail(
            post.screenshot_image,
            '1280x1000',
            quality=90
        ).url
        if context['screenshot_image'].startswith('//'):
            # facebook is not going to like that
            context['screenshot_image'] = (
                'https:' + context['screenshot_image']
            )
    else:
        context['screenshot_image'] = None

    comments = (
        BlogComment.objects
        .filter(blogitem=post)
        .order_by('add_date')
    )
    if not request.user.is_staff:
        comments = comments.filter(approved=True)

    comments_truncated = False
    if request.GET.get('comments') != 'all':
        comments = comments[:settings.MAX_INITIAL_COMMENTS]
        if post.count_comments() > settings.MAX_INITIAL_COMMENTS:
            comments_truncated = settings.MAX_INITIAL_COMMENTS

    all_comments = defaultdict(list)
    for comment in comments:
        all_comments[comment.parent_id].append(comment)
    context['comments_truncated'] = comments_truncated
    context['all_comments'] = all_comments
    context['related_by_keyword'] = get_related_posts_by_keyword(post, limit=5)
    context['related_by_text'] = get_related_posts_by_text(post, limit=5)
    context['show_buttons'] = (
        not screenshot_mode and
        not settings.DEBUG and
        request.path != '/plog/blogitem-040601-1'
    )
    context['show_fusion_ad'] = (
        not screenshot_mode and
        not settings.DEBUG
    )
    context['home_url'] = request.build_absolute_uri('/')
    context['page_title'] = post.title
    context['pub_date_years'] = THIS_YEAR - post.pub_date.year
    return render(request, 'plog/post.html', context)


@cache_control(public=True, max_age=7 * 24 * 60 * 60)
@cache_page(
    ONE_WEEK,
    _blog_post_key_prefixer
)
def all_blog_post_comments(request, oid):

    # temporary debugging
    if request.method == 'GET':
        print("all_blog_post_comments.MISS (%r, %r, %s)" % (
            request.path,
            request.META.get('QUERY_STRING'),
            timezone.now().isoformat()
        ))

    post = get_object_or_404(BlogItem, oid=oid)
    comments = (
        BlogComment.objects
        .filter(blogitem=post)
        .order_by('add_date')
    )
    if not request.user.is_staff:
        comments = comments.filter(approved=True)

    all_comments = defaultdict(list)
    for comment in comments:
        all_comments[comment.parent_id].append(comment)
    data = {
        'post': post,
        'all_comments': all_comments
    }
    return render(request, 'plog/_all_comments.html', data)


def get_related_posts_by_keyword(post, limit=5):
    if not post.proper_keywords:
        return BlogItem.objects.none()
    return BlogItem.objects.filter(
        proper_keywords__overlap=post.proper_keywords,
        pub_date__lt=timezone.now()
    ).exclude(
        id=post.id,
    ).order_by('-pub_date')[:limit]


def get_related_posts_by_text(post, limit=5):
    search = BlogItemDoc.search()
    search.update_from_dict({
        'query': {
            'more_like_this': {
                'fields': ['title', 'text'],
                'like': [{
                    '_index': settings.ES_INDEX,
                    '_type': 'blog_item_doc',
                    '_id': post.id,
                }],
                'min_term_freq': 2,
                'min_doc_freq': 5,
                'min_word_length': 3,
                'max_query_terms': 25,
            }
        }
    })
    search = search[:limit]
    response = search.execute()
    ids = [int(x._id) for x in response]
    print('Took {:.1f}ms to find {} related by text'.format(
        response.took,
        response.hits.total,
    ))
    if not ids:
        return []
    objects = BlogItem.objects.filter(
        pub_date__lt=timezone.now(),
        id__in=ids
    )
    return sorted(
        objects,
        key=lambda x: ids.index(x.id)
    )


def _render_comment(comment):
    return render_to_string('plog/comment.html', {'comment': comment})


@ensure_csrf_cookie
@json_view
def prepare_json(request):
    data = {
        'csrf_token': request.META["CSRF_COOKIE"],
    }
    return http.JsonResponse(data)


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
@transaction.atomic
def submit_json(request, oid):
    post = get_object_or_404(BlogItem, oid=oid)
    if post.disallow_comments:
        return http.HttpResponseBadRequest("No comments please")
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

        if request.user.is_authenticated():
            _approve_comment(blog_comment)
            assert blog_comment.approved
        else:
            tos = [x[1] for x in settings.ADMINS]
            from_ = ['%s <%s>' % x for x in settings.ADMINS][0]
            body = _get_comment_body(post, blog_comment)
            send_mail("Peterbe.com: New comment on '%s'" % post.title,
                      body, from_, tos)

    html = render_to_string('plog/comment.html', {
        'comment': blog_comment,
        'preview': True,
    })
    _comments = BlogComment.objects.filter(approved=True, blogitem=post)
    comment_count = _comments.count() + 1
    data = {
        'html': html,
        'parent': parent and parent.oid or None,
        'comment_count': comment_count,
    }

    response = http.JsonResponse(data)
    return response


@login_required
def approve_comment(request, oid, comment_oid):
    try:
        blogitem = BlogItem.objects.get(oid=oid)
    except BlogItem.DoesNotExist:
        return http.HttpResponse("BlogItem {!r} can't be found".format(
            oid
        ), status=404)
    try:
        blogcomment = BlogComment.objects.get(oid=comment_oid)
        if blogcomment.approved:
            url = blogitem.get_absolute_url()
            if blogcomment.blogitem:
                url += '#%s' % blogcomment.oid
            return http.HttpResponse(
                '''<html>Comment already approved<br>
                <a href="{}">{}</a>
                </html>
                '''.format(url, blogitem.title)
            )
    except BlogComment.DoesNotExist:
        return http.HttpResponse("BlogComment {!r} can't be found".format(
            comment_oid
        ), status=404)
    if blogcomment.blogitem != blogitem:
        raise http.Http404("bad rel")

    forbidden = _check_auth_key(request, blogitem, blogcomment)
    if forbidden:
        return forbidden

    _approve_comment(blogcomment)

    if request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
        return http.HttpResponse('OK')
    else:
        url = blogitem.get_absolute_url()
        if blogcomment.blogitem:
            url += '#%s' % blogcomment.oid
        return http.HttpResponse(
            '''<html>Comment approved<br>
            <a href="{}">{}</a>
            </html>
            '''.format(url, blogitem.title)
        )


def _check_auth_key(request, blogitem, blogcomment):
    # Temporary thing. Delete this end of 2017.
    start_date = timezone.make_aware(datetime.datetime(2017, 9, 24))
    if blogcomment.add_date < start_date:
        return
    key = request.GET.get('key')
    if not key:
        return http.HttpResponseForbidden('No key')
    try:
        found = OneTimeAuthKey.objects.get(
            key=key,
            blogitem=blogitem,
            blogcomment=blogcomment,
            used__isnull=True
        )
        found.used = timezone.now()
        found.save()
    except OneTimeAuthKey.DoesNotExist:
        return http.HttpResponseForbidden('Key not found or already used')


def _approve_comment(blogcomment):
    blogcomment.approved = True
    blogcomment.save()

    if (
        blogcomment.parent and blogcomment.parent.email and
        valid_email(blogcomment.parent.email) and
        blogcomment.email != blogcomment.parent.email
    ):
        parent = blogcomment.parent
        tos = [parent.email]
        from_ = 'Peterbe.com <mail@peterbe.com>'
        body = _get_comment_reply_body(
            blogcomment.blogitem,
            blogcomment,
            parent
        )
        subject = 'Peterbe.com: Reply to your comment'
        send_mail(subject, body, from_, tos)


def _get_comment_body(blogitem, blogcomment):
    base_url = 'https://%s' % Site.objects.get_current().domain
    approve_url = reverse(
        'approve_comment', args=[blogitem.oid, blogcomment.oid]
    )
    approve_url += '?key={}'.format(
        OneTimeAuthKey.objects.create(
            blogitem=blogitem,
            blogcomment=blogcomment
        ).key
    )
    delete_url = reverse(
        'delete_comment', args=[blogitem.oid, blogcomment.oid]
    )
    delete_url += '?key={}'.format(
        OneTimeAuthKey.objects.create(
            blogitem=blogitem,
            blogcomment=blogcomment
        ).key
    )
    template = loader.get_template('plog/comment_body.txt')
    context = {
        'post': blogitem,
        'comment': blogcomment,
        'approve_url': approve_url,
        'delete_url': delete_url,
        'base_url': base_url,
    }
    return template.render(context).strip()


def _get_comment_reply_body(blogitem, blogcomment, parent):
    base_url = 'https://%s' % Site.objects.get_current().domain
    template = loader.get_template('plog/comment_reply_body.txt')
    context = {
        'post': blogitem,
        'comment': blogcomment,
        'parent': parent,
        'base_url': base_url,
    }
    return template.render(context).strip()


@login_required
def delete_comment(request, oid, comment_oid):
    user = request.user
    assert user.is_staff or user.is_superuser
    try:
        blogitem = BlogItem.objects.get(oid=oid)
    except BlogItem.DoesNotExist:
        return http.HttpResponse("BlogItem {!r} can't be found".format(
            oid
        ), status=404)
    try:
        blogcomment = BlogComment.objects.get(oid=comment_oid)
    except BlogComment.DoesNotExist:
        return http.HttpResponse("BlogComment {!r} can't be found".format(
            comment_oid
        ), status=404)
    if blogcomment.blogitem != blogitem:
        raise http.Http404("bad rel")

    forbidden = _check_auth_key(request, blogitem, blogcomment)
    if forbidden:
        return forbidden

    blogcomment.delete()

    url = blogitem.get_absolute_url()
    return http.HttpResponse(
        '''<html>Comment deleted<br>
        <a href="{}">{}</a>
        </html>
        '''.format(url, blogitem.title)
    )


def _plog_index_key_prefixer(request):
    if request.method != 'GET':
        return None
    if request.user.is_authenticated():
        return None
    prefix = utils.make_prefix(request.GET)
    cache_key = 'latest_post_modify_date'
    latest_date = cache.get(cache_key)
    if latest_date is None:
        latest, = (BlogItem.objects
                   .order_by('-modify_date')
                   .values('modify_date')[:1])
        latest_date = latest['modify_date'].strftime('%f')
        cache.set(cache_key, latest_date, ONE_DAY)
    prefix += str(latest_date)
    return prefix


@cache_control(public=True, max_age=60 * 60)
@cache_page(
    ONE_DAY,
    _plog_index_key_prefixer,
)
def plog_index(request):
    groups = defaultdict(list)
    now = utc_now()
    group_dates = []

    _categories = dict(
        (x.pk, x.name) for x in
        Category.objects.all()
    )
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
        'page_title': 'Blog archive',
    }
    return render(request, 'plog/index.html', data)


def _new_comment_key_prefixer(request):
    if request.method != 'GET':
        return None
    if request.user.is_authenticated():
        return None
    prefix = utils.make_prefix(request.GET)
    cache_key = 'latest_comment_add_date'
    latest_date = cache.get(cache_key)
    if latest_date is None:
        latest, = (BlogItem.objects
                   .order_by('-modify_date')
                   .values('modify_date')[:1])
        latest_date = latest['modify_date'].strftime('%f')
        cache.set(cache_key, latest_date, 60 * 60)
    prefix += str(latest_date)
    return prefix


@cache_page(ONE_HOUR, _new_comment_key_prefixer)
def new_comments(request):
    context = {}
    comments = BlogComment.objects.all()
    if not request.user.is_authenticated():
        comments = comments.filter(approved=True)

    # legacy stuff that can be removed in march 2012
    for c in comments.filter(blogitem__isnull=True):
        if not c.parent:
            c.delete()
        else:
            c.correct_blogitem_parent()

    context['comments'] = (
        comments
        .order_by('-add_date')
        .select_related('blogitem')[:50]
    )
    context['page_title'] = 'Latest new blog comments'
    return render(request, 'plog/new-comments.html', context)


@login_required
@transaction.atomic
def add_post(request):
    context = {}
    user = request.user
    assert user.is_staff or user.is_superuser
    if request.method == 'POST':
        form = BlogForm(data=request.POST)
        if form.is_valid():
            assert isinstance(form.cleaned_data['proper_keywords'], list)
            blogitem = BlogItem.objects.create(
                oid=form.cleaned_data['oid'],
                title=form.cleaned_data['title'],
                text=form.cleaned_data['text'],
                summary=form.cleaned_data['summary'],
                display_format=form.cleaned_data['display_format'],
                codesyntax=form.cleaned_data['codesyntax'],
                url=form.cleaned_data['url'],
                pub_date=form.cleaned_data['pub_date'],
                proper_keywords=form.cleaned_data['proper_keywords'],
            )
            for category in form.cleaned_data['categories']:
                blogitem.categories.add(category)
            blogitem.save()

            url = reverse('edit_post', args=[blogitem.oid])
            return redirect(url)
    else:
        initial = {
            'pub_date': utc_now() + datetime.timedelta(seconds=60 * 60),
            'display_format': 'markdown',
        }
        form = BlogForm(initial=initial)
    context['form'] = form
    context['page_title'] = 'Add post'
    context['blogitem'] = None
    return render(request, 'plog/edit.html', context)


@login_required
@transaction.atomic
def edit_post(request, oid):
    blogitem = get_object_or_404(BlogItem, oid=oid)
    data = {}
    user = request.user
    assert user.is_staff or user.is_superuser
    if request.method == 'POST':
        form = BlogForm(instance=blogitem, data=request.POST)
        if form.is_valid():
            blogitem.oid = form.cleaned_data['oid']
            blogitem.title = form.cleaned_data['title']
            blogitem.text = form.cleaned_data['text']
            blogitem.text_rendered = ''
            blogitem.summary = form.cleaned_data['summary']
            blogitem.display_format = form.cleaned_data['display_format']
            blogitem.codesyntax = form.cleaned_data['codesyntax']
            blogitem.pub_date = form.cleaned_data['pub_date']
            assert isinstance(form.cleaned_data['proper_keywords'], list)
            blogitem.proper_keywords = form.cleaned_data['proper_keywords']
            blogitem.categories.clear()
            for category in form.cleaned_data['categories']:
                blogitem.categories.add(category)
            blogitem.save()

            url = reverse('edit_post', args=[blogitem.oid])
            return redirect(url)

    else:
        form = BlogForm(instance=blogitem)
    data['form'] = form
    data['page_title'] = 'Edit post'
    data['blogitem'] = blogitem
    data['INBOUND_EMAIL_ADDRESS'] = settings.INBOUND_EMAIL_ADDRESS
    return render(request, 'plog/edit.html', data)


@csrf_exempt
@login_required
@require_POST
def preview_post(request):
    from django.template import Context
    from django.template.loader import get_template

    post_data = dict()
    for key, value in request.POST.items():
        if value:
            post_data[key] = value
    post_data['categories'] = request.POST.getlist('categories[]')
    post_data['oid'] = 'doesntmatter'
    post_data['keywords'] = []
    form = BlogForm(data=post_data)
    if not form.is_valid():
        return http.HttpResponse(str(form.errors))

    class MockPost(object):

        def count_comments(self):
            return 0

        def has_carousel_tag(self):
            return False

        @property
        def rendered(self):
            if self.display_format == 'structuredtext':
                return utils.stx_to_html(self.text, self.codesyntax)
            else:
                return utils.markdown_to_html(self.text, self.codesyntax)

    post = MockPost()
    post.title = form.cleaned_data['title']
    post.text = form.cleaned_data['text']
    post.display_format = form.cleaned_data['display_format']
    post.codesyntax = form.cleaned_data['codesyntax']
    post.url = form.cleaned_data['url']
    post.pub_date = form.cleaned_data['pub_date']
    post.categories = Category.objects.filter(
        pk__in=form.cleaned_data['categories']
    )
    template = get_template("plog/_post.html")
    context = Context({'post': post})
    return http.HttpResponse(template.render(context))


@login_required
@transaction.atomic
def add_file(request):
    data = {}
    user = request.user
    assert user.is_staff or user.is_superuser
    if request.method == 'POST':
        form = BlogFileUpload(request.POST, request.FILES)
        if form.is_valid():
            instance = form.save()
            url = reverse('edit_post', args=[instance.blogitem.oid])
            return redirect(url)
    else:
        initial = {}
        if request.GET.get('oid'):
            blogitem = get_object_or_404(
                BlogItem,
                oid=request.GET.get('oid')
            )
            initial['blogitem'] = blogitem
        form = BlogFileUpload(initial=initial)
    data['form'] = form
    return render(request, 'plog/add_file.html', data)


@login_required
def post_thumbnails(request, oid):
    blogitem = get_object_or_404(BlogItem, oid=oid)
    blogfiles = (
        BlogFile.objects
        .filter(blogitem=blogitem)
        .order_by('add_date')
    )

    images = []

    for blogfile in blogfiles:
        full_im = thumbnail(
            blogfile.file,
            '1000x1000',
            upscale=False,
            quality=100
        )
        full_url = full_im.url
        delete_url = reverse('delete_post_thumbnail', args=(blogfile.pk,))
        image = {
            'full_url': full_url,
            'delete_url': delete_url,
        }
        formats = (
            ('small', '120x120'),
            ('big', '230x230'),
            ('bigger', '370x370'),  # iPhone 6 is 375
        )
        for key, geometry in formats:
            im = thumbnail(
                blogfile.file,
                geometry,
                quality=81
            )
            url_ = im.url
            image[key] = {
                'url': url_,
                'alt': getattr(blogfile, 'title', blogitem.title),
                'width': im.width,
                'height': im.height,
            }
        images.append(image)
    return http.JsonResponse({'images': images})


@login_required
@require_POST
def delete_post_thumbnail(request, pk):
    blogfile = get_object_or_404(BlogFile, pk=pk)
    blogfile.delete()
    return http.JsonResponse({'ok': True})


@cache_page(ONE_DAY)
def calendar(request):
    context = {'page_title': 'Archive calendar'}
    return render(request, 'plog/calendar.html', context)


@json_view
def calendar_data(request):
    form = CalendarDataForm(request.GET)
    if not form.is_valid():
        return http.HttpResponseBadRequest(form.errors)
    start = form.cleaned_data['start']
    end = form.cleaned_data['end']
    if not request.user.is_authenticated():
        end = min(end, timezone.now())
        if end < start:
            return []

    qs = BlogItem.objects.filter(pub_date__gte=start, pub_date__lt=end)
    items = []
    for each in qs:
        item = {
            'title': each.title,
            'start': each.pub_date,
            'url': reverse('blog_post', args=[each.oid]),
            'className': 'post',
        }
        items.append(item)

    return items


def plog_hits(request):
    context = {}
    limit = int(request.GET.get('limit', 50))
    _category_names = dict(
        (x['id'], x['name'])
        for x in Category.objects.all().values('id', 'name')
    )
    categories = defaultdict(list)
    qs = (
        BlogItem.categories.through.objects.all()
        .values('blogitem_id', 'category_id')
    )
    for each in qs:
        categories[each['blogitem_id']].append(
            _category_names[each['category_id']]
        )
    context['categories'] = categories
    query = BlogItem.objects.raw("""
        WITH counts AS (
            SELECT
                blogitem_id, count(blogitem_id) AS count
                FROM plog_blogitemhit
                GROUP BY blogitem_id
        )
        SELECT
            b.id, b.oid, b.title, count AS hits, b.pub_date,
            EXTRACT(DAYS FROM (NOW() - b.pub_date))::INT AS age,
            count / EXTRACT(DAYS FROM (NOW() - b.pub_date)) AS score
        FROM counts, plog_blogitem b
        WHERE
            blogitem_id = b.id AND (NOW() - b.pub_date) > INTERVAL '1 day'
        ORDER BY score desc
        LIMIT {limit}
    """.format(limit=limit))
    context['all_hits'] = query

    category_scores = defaultdict(list)
    for item in query:
        for cat in categories[item.id]:
            category_scores[cat].append(item.score)

    summed_category_scores = []
    for name, scores in category_scores.items():
        count = len(scores)
        summed_category_scores.append({
            'name': name,
            'count': count,
            'sum': sum(scores),
            'avg': sum(scores) / count,
            'med': median(scores),
        })
    context['summed_category_scores'] = summed_category_scores
    context['page_title'] = 'Hits'
    return render(request, 'plog/plog_hits.html', context)


def plog_hits_data(request):
    hits = {}

    def get_count(start, end):
        return BlogItemHit.objects.filter(
            add_date__gte=start,
            add_date__lt=end,
        ).count()

    now = timezone.now()

    hits['last_hour'] = get_count(
        now - datetime.timedelta(hours=1),
        now
    )
    now = now.replace(hour=0, minute=0, second=0)
    hits['today'] = get_count(
        now - datetime.timedelta(days=1),
        now
    )
    hits['yesterday'] = get_count(
        now - datetime.timedelta(days=2),
        now - datetime.timedelta(days=1)
    )
    hits['last_week'] = get_count(
        now - datetime.timedelta(days=1 + 7),
        now - datetime.timedelta(days=7)
    )
    hits['last_month'] = get_count(
        now - datetime.timedelta(days=1 + 30),
        now - datetime.timedelta(days=30)
    )

    return http.JsonResponse({'hits': hits})
