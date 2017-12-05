import markdown
import time
import datetime
import json
import functools
import hashlib
import re
from urllib.parse import urlencode

import zope.structuredtext
from pygments import highlight
from pygments import lexers
from pygments.formatters import HtmlFormatter
from pygmentslexerbabylon import BabylonLexer
from django.conf import settings
from django import http
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.utils import timezone
from .gfm import gfm

# XXX this escape.py is copied from
# https://github.com/tornadoweb/tornado/blob/master/tornado/escape.py
# and it works but it's an ugly copy and perhaps better done
# with using bleach.
from .escape import linkify


def is_bot(ua='', ip=None):
    if 'bot' not in ua.lower() and 'download-all-plogs.py' not in ua:
        return False

    return True


def make_prefix(request_dict, max_length=100, hash_request_values=False):
    _get = dict(request_dict)

    def stringify(s):
        if isinstance(s, str):
            s = s.encode('utf-8')
        if hash_request_values:
            return hashlib.md5(s).hexdigest()
        return s

    for key, value in _get.items():
        _get[key] = [stringify(x) for x in value]
    url_encoded = urlencode(_get, True)
    if len(url_encoded) > max_length:
        if hash_request_values:
            # Still too darn long!
            return stringify(url_encoded)
        else:
            # Try again by md5 hashing each value
            return make_prefix(
                request_dict,
                max_length=max_length,
                hash_request_values=True
            )
    return url_encoded


def utc_now():
    return timezone.now()


def valid_email(value):
    try:
        validate_email(value)
        return True
    except ValidationError:
        return False


whitespace_start_regex = re.compile(r'^\n*(\s+)', re.M)


def render_comment_text(text):
    html = linkify(text, extra_params=' rel="nofollow"')

    # So you can write comments with code with left indentation whitespace
    def subber(m):
        return m.group().replace(' ', u'&nbsp;')
    html = whitespace_start_regex.sub(subber, html)

    html = html.replace('\n', '<br>')
    return html


def stx_to_html(text, codesyntax):
    rendered = zope.structuredtext.stx2html(
        text,
        header=0
    )

    _regex = re.compile(r'(<pre>(.*?)</pre>)', re.DOTALL)

    lexer = _get_lexer(codesyntax)

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

    return _regex.sub(match, rendered)


def _get_lexer(codesyntax):
    if codesyntax in ('cpp', 'javascript'):
        return lexers.JavascriptLexer()
    elif codesyntax == 'python':
        return lexers.PythonLexer()
    elif codesyntax == 'xml' or codesyntax == 'html':
        return lexers.HtmlLexer()
    elif codesyntax == 'css':
        return lexers.CssLexer()
    elif codesyntax == 'sql':
        return lexers.SqlLexer()
    elif codesyntax == 'bash':
        return lexers.BashLexer()
    elif codesyntax == 'go':
        return lexers.GoLexer()
    elif codesyntax == 'jsx':
        return BabylonLexer()
    elif codesyntax:
        raise NotImplementedError(codesyntax)
    else:
        return lexers.TextLexer()


_codesyntax_regex = re.compile(
    '```(python|cpp|javascript|xml|html|css|sql|bash|go|jsx)'
)
_markdown_pre_regex = re.compile('```([^`]+)```')


def markdown_to_html(text, codesyntax):
    def matcher(match):
        found = match.group()
        try:
            codesyntax = _codesyntax_regex.findall(found)[0]
        except IndexError:
            codesyntax = None
        found = _codesyntax_regex.sub('```', found)
        if codesyntax:
            def highlighter(m):
                lexer = _get_lexer(codesyntax)
                code = m.group().replace('```', '')
                return highlight(code, lexer, HtmlFormatter())
            found = _markdown_pre_regex.sub(highlighter, found)
        found = found.replace('```', '<pre>', 1)
        found = found.replace('```', '</pre>')
        return found

    text = _markdown_pre_regex.sub(matcher, text)
    html = markdown.markdown(
        gfm(text),
        extensions=['markdown.extensions.tables']
    )
    html = html.replace('<table>', '<table class="ui celled table">')
    return html


_SRC_regex = re.compile('(src|href)="([^"]+)"')
_image_extension_regex = re.compile('\.(png|jpg|jpeg|gif)$', re.I)


# Note: this is quite experimental still
def cache_prefix_files(text):
    hash_ = str(int(time.time()))
    static_url = settings.STATIC_URL.replace('/static/', '/')
    prefix = '%sCONTENTCACHE-%s' % (static_url, hash_)
    assert not prefix.endswith('/')

    def matcher(match):
        attr, url = match.groups()
        if (
            url.startswith('/') and
            not url.startswith('//') and
            '://' not in url and
            _image_extension_regex.findall(url)
        ):
            url = '%s%s' % (prefix, url)
        return '%s="%s"' % (attr, url)

    return _SRC_regex.sub(matcher, text)


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        return json.JSONEncoder.default(self, obj)


def json_view(f):
    @functools.wraps(f)
    def wrapper(*args, **kw):
        response = f(*args, **kw)
        if isinstance(response, http.HttpResponse):
            return response
        else:
            r = http.HttpResponse(
                json.dumps(response, cls=DateTimeEncoder, indent=2),
                content_type='application/json'
            )
            r.write('\n')
            return r
    return wrapper


def view_function_timer(func):

    @functools.wraps(func)
    def inner(*args, **kwargs):
        try:
            t0 = time.time()
            return func(*args, **kwargs)
        finally:
            t1 = time.time()
            print(
                'View Function',
                func.__name__,
                args[1:],
                'Took',
                '{:.2f}ms'.format(1000 * (t1 - t0)),
            )
    return inner
