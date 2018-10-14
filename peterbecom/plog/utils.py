import markdown
import time
import datetime
import json
import functools
import hashlib
import re
from urllib.parse import urlencode, urlparse
from html import escape

import bleach
import requests
from requests.exceptions import ConnectionError
import zope.structuredtext
from pygments import highlight
from pygments import lexers
from pygments.formatters import HtmlFormatter
from pygmentslexerbabylon import BabylonLexer
from bleach.linkifier import Linker

from django.conf import settings
from django import http
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.utils import timezone
from .gfm import gfm


def is_bot(ua="", ip=None):
    if "bot" not in ua.lower() and "download-all-plogs.py" not in ua:
        return False
    if "HeadlessChrome/" in ua:
        return True

    return True


def make_prefix(request_dict, max_length=100, hash_request_values=False):
    _get = dict(request_dict)

    def stringify(s):
        if isinstance(s, str):
            s = s.encode("utf-8")
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
                request_dict, max_length=max_length, hash_request_values=True
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


whitespace_start_regex = re.compile(r"^\n*(\s+)", re.M)


def render_comment_text(text):

    html = bleach.clean(text)

    def custom_nofollow_maker(attrs, new=False):
        href_key = (None, "href")

        if href_key not in attrs:
            return attrs

        href = attrs[href_key]
        if href.startswith("mailto:") or href.startswith("tel:"):
            # Leave untouched
            return attrs
        if not (href.startswith("http:") or href.startswith("https:")):
            # Bail if it's not a HTTP URL, such as ssh:// or ftp://
            return None

        p = urlparse(href)
        if p.netloc not in settings.NOFOLLOW_EXCEPTIONS:
            # Before we add the `rel="nofollow"` let's first check that this is a
            # valid domain at all.
            root_url = p.scheme + "://" + p.netloc
            try:
                response = requests.head(root_url, timeout=5)
                if response.status_code == 301:
                    redirect_p = urlparse(response.headers["location"])
                    # If the only difference is that it redirects to https instead
                    # of http, then amend the href.
                    if (
                        redirect_p.scheme == "https"
                        and p.scheme == "http"
                        and p.netloc == redirect_p.netloc
                    ):
                        attrs[href_key] = href.replace("http://", "https://")

            except ConnectionError:
                return None

            rel_key = (None, "rel")
            rel_values = [val for val in attrs.get(rel_key, "").split(" ") if val]
            if "nofollow" not in [rel_val.lower() for rel_val in rel_values]:
                rel_values.append("nofollow")
            attrs[rel_key] = " ".join(rel_values)

        return attrs

    html = bleach.linkify(html, callbacks=[custom_nofollow_maker])

    # So you can write comments with code with left indentation whitespace
    def subber(m):
        return m.group().replace(" ", "&nbsp;")

    html = whitespace_start_regex.sub(subber, html)

    html = html.replace("\n", "<br>")
    return html


def stx_to_html(text, codesyntax):
    rendered = zope.structuredtext.stx2html(text, header=0)

    _regex = re.compile(r"(<pre>(.*?)</pre>)", re.DOTALL)

    lexer = _get_lexer(codesyntax)

    def match(s):
        outer, inner = s.groups()
        new_inner = inner
        new_inner = new_inner.replace("&gt;", ">").replace("&lt;", "<")
        lines = new_inner.splitlines()
        lines = [re.sub("^\s", "", x) for x in lines]
        new_inner = "\n".join(lines)
        if lexer:
            new_inner = highlight(new_inner, lexer, HtmlFormatter())
        # else:
        #     print("NO LEXER FOR......................................")
        #     print(new_inner)
        return new_inner

    return _regex.sub(match, rendered)


def _get_lexer(codesyntax):
    if codesyntax in ("cpp", "javascript"):
        return lexers.JavascriptLexer()
    elif codesyntax == "python":
        return lexers.PythonLexer()
    elif codesyntax == "json":
        return lexers.JsonLexer()
    elif codesyntax == "xml" or codesyntax == "html":
        return lexers.HtmlLexer()
    elif codesyntax == "yml" or codesyntax == "yaml":
        return lexers.YamlLexer()
    elif codesyntax == "css":
        return lexers.CssLexer()
    elif codesyntax == "sql":
        return lexers.SqlLexer()
    elif codesyntax == "bash" or codesyntax == "sh":
        return lexers.BashLexer()
    elif codesyntax == "go":
        return lexers.GoLexer()
    elif codesyntax == "rust":
        return lexers.RustLexer()
    elif codesyntax == "jsx":
        return BabylonLexer()
    elif codesyntax:
        raise NotImplementedError(codesyntax)
    else:
        return lexers.TextLexer()


_codesyntax_regex = re.compile(
    "```(python|cpp|javascript|json|xml|html|yml|yaml|css|sql|sh|bash|go|jsx|rust)"  # noqa
)
_markdown_pre_regex = re.compile(r"(```(.*?)```)", re.M | re.DOTALL)


def markdown_to_html(text, codesyntax):
    def matcher(match):
        found = match.group()
        try:
            codesyntax = _codesyntax_regex.findall(found)[0]
        except IndexError:
            codesyntax = None
        found = _codesyntax_regex.sub("```", found)
        if codesyntax:

            def highlighter(m):
                lexer = _get_lexer(codesyntax)
                code = m.group().replace("```", "")
                return highlight(code, lexer, HtmlFormatter())

            found = _markdown_pre_regex.sub(highlighter, found)
        else:

            def highlighter(m):
                meat = m.groups()[1]
                return "<pre>{}</pre>".format(escape(meat.strip()))

            found = _markdown_pre_regex.sub(highlighter, found)
        return found

    text = _markdown_pre_regex.sub(matcher, text)
    html = markdown.markdown(gfm(text), extensions=["markdown.extensions.tables"])
    html = html.replace("<table>", '<table class="ui celled table">')
    html = html.replace("<pre><span></span>", "<pre>")
    return html


_SRC_regex = re.compile('(src|href)="([^"]+)"')
_image_extension_regex = re.compile("\.(png|jpg|jpeg|gif)$", re.I)


# Note: this is quite experimental still
def cache_prefix_files(text):
    hash_ = str(int(time.time()))
    static_url = settings.STATIC_URL.replace("/static/", "/")
    prefix = "%sCONTENTCACHE-%s" % (static_url, hash_)
    assert not prefix.endswith("/")

    def matcher(match):
        attr, url = match.groups()
        if (
            url.startswith("/")
            and not url.startswith("//")
            and "://" not in url
            and _image_extension_regex.findall(url)
        ):
            url = "%s%s" % (prefix, url)
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
                content_type="application/json",
            )
            r.write("\n")
            return r

    return wrapper


def view_function_timer(prefix="", writeto=print):
    def decorator(func):
        @functools.wraps(func)
        def inner(*args, **kwargs):
            try:
                t0 = time.time()
                return func(*args, **kwargs)
            finally:
                t1 = time.time()
                writeto(
                    "View Function",
                    "({})".format(prefix) if prefix else "",
                    func.__name__,
                    args[1:],
                    "Took",
                    "{:.2f}ms".format(1000 * (t1 - t0)),
                    args[0].build_absolute_uri(),
                )

        return inner

    return decorator


def rate_blog_comment(comment):

    result = {"good": {}, "bad": {}}

    if len(comment.comment) > 500:
        result["bad"]["length"] = ">500 characters"

    # Exclude comments that have links in them unless the links are to
    # www.peterbe.com or songsear.ch.
    links = []

    def find_links(attrs, new=False):
        href = attrs[(None, u"href")]
        p = urlparse(href)
        if p.netloc not in ["www.peterbe.com", "songsear.ch"]:
            links.append(href)

    linker = Linker(callbacks=[find_links])
    linker.linkify(comment.comment)

    if links:
        result["bad"]["links"] = links

    GOOD_STRINGS = settings.PLOG_GOOD_STRINGS
    BAD_STRINGS = settings.PLOG_BAD_STRINGS

    good_strings = [x for x in GOOD_STRINGS if x in comment.comment]
    maybe_good_strings = [
        x for x in GOOD_STRINGS if x.lower() in comment.comment.lower()
    ]

    bad_strings = [x for x in BAD_STRINGS if x in comment.comment]
    maybe_bad_strings = [x for x in BAD_STRINGS if x.lower() in comment.comment.lower()]

    if good_strings:
        result["good"]["strings"] = good_strings
    elif maybe_good_strings:
        result["good"]["maybe_strings"] = maybe_good_strings

    if bad_strings:
        result["bad"]["strings"] = bad_strings
    elif maybe_bad_strings:
        result["bad"]["maybe_strings"] = maybe_bad_strings

    return result
