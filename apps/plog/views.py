import datetime
import re
import functools
import json
from pprint import pprint
from django import http
from django.shortcuts import render, get_object_or_404
from django.template.loader import render_to_string
from .models import BlogItem, BlogComment, Category
import zope.structuredtext

from pygments import highlight
from pygments.lexers import PythonLexer, JavascriptLexer, TextLexer
from pygments.formatters import HtmlFormatter
from .utils import render_comment_text


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
    try:
        post = BlogItem.objects.get(oid=oid)
    except BlogItem.DoesNotExist:
        try:
            post = BlogItem.objects.get(oid__iexact=oid)
        except BlogItem.DoesNotExist:
            raise http.Http404(oid)
    if not post.text_rendered:
        if post.display_format == 'structuredtext':
            post.text_rendered = _stx_to_html(post.text, post.codesyntax)
        else:
            raise NotImplementedError(post.display_format)
        #post.save()
    data = {
      'post': post,
#      'comments_html':
#          '\n'.join(_render_comments(post)),
    }
    return render(request, 'plog/post.html', data)

def _render_comments(parent):
    html = []
    if parent.__class__ == BlogItem:
        filter_ = {'blogitem': parent}
    else:
        filter_ = {'parent': parent}
    for comment in BlogComment.objects.filter(**filter_).order_by('add_date'):
        html.append(_render_comment(comment))
        html.extend(_render_comments(comment))
    return html

def _render_comment(comment):
    return render_to_string('plog/comment.html', {'comment': comment})

def _stx_to_html(text, codesyntax):
    rendered = zope.structuredtext.stx2html(
      text,
      header=0
    )
    _regex = re.compile(r'(<pre>(.*?)</pre>)', re.DOTALL)

    if codesyntax == 'cpp':
        lexer = JavascriptLexer()
    elif codesyntax == 'python':
        lexer = PythonLexer()
    elif codesyntax:
        raise NotImplementedError(codesyntax)
    else:
        lexer = TextLexer()

    def match(s):
        outer, inner = s.groups()
        new_inner = inner
        new_inner = (new_inner
                     .replace('&gt;', '>')
                     .replace('&lt;', '<')
                     )
        lines = new_inner.splitlines()
        lines = [re.sub('^\s', '', x) for x in lines]
        new_inner = '\n'.join(lines)
        if lexer:
            new_inner = highlight(new_inner, lexer, HtmlFormatter())
        return new_inner

        return outer.replace(inner, new_inner)
    return _regex.sub(match, rendered)


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

# XXX POST only
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


# XXX POST only
@json_view
def submit_json(request, oid):
    post = get_object_or_404(BlogItem, oid=oid)
    comment = request.POST['comment'].strip()
    name = request.POST.get('name', u'').strip()
    email = request.POST.get('email', u'').strip()
    parent = request.POST.get('parent')
    if parent:
        parent = get_object_or_404(BlogComment, oid=parent)

    search = {'comment': comment}
    if name:
        search['name'] = name
        request.COOKIES['name'] = name
    if email:
        search['email'] = email
        request.COOKIES['email'] = email
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
        )
    html = render_to_string('plog/comment.html', {
      'comment': comment,
      'preview': False,
    })
    return {'html': html, 'parent': parent and parent.oid or None}
