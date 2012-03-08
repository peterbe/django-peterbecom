import markdown
import time
import datetime
import re
import zope.structuredtext
from pygments import highlight
from pygments.lexers import (PythonLexer, JavascriptLexer, TextLexer,
  HtmlLexer, CssLexer, SqlLexer)
from pygments.formatters import HtmlFormatter
from django.conf import settings
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from isodate import UTC
from gfm import gfm


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


def valid_email(value):
    try:
        validate_email(value)
        return True
    except ValidationError:
        return False


_BASESTRING_TYPES = (basestring, type(None))
def to_basestring(value):
    """Converts a string argument to a subclass of basestring.

    In python2, byte and unicode strings are mostly interchangeable,
    so functions that deal with a user-supplied argument in combination
    with ascii string constants can use either and should return the type
    the user supplied.  In python3, the two types are not interchangeable,
    so this method is needed to convert byte strings to unicode.
    """
    if isinstance(value, _BASESTRING_TYPES):
        return value
    assert isinstance(value, bytes)
    return value.decode("utf-8")

_TO_UNICODE_TYPES = (unicode, type(None))
def to_unicode(value):
    """Converts a string argument to a unicode string.

    If the argument is already a unicode string or None, it is returned
    unchanged.  Otherwise it must be a byte string and is decoded as utf8.
    """
    if isinstance(value, _TO_UNICODE_TYPES):
        return value
    assert isinstance(value, bytes)
    return value.decode("utf-8")

# to_unicode was previously named _unicode not because it was private,
# but to avoid conflicts with the built-in unicode() function/type
_unicode = to_unicode


_XHTML_ESCAPE_RE = re.compile('[&<>"]')
_XHTML_ESCAPE_DICT = {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}
def xhtml_escape(value):
    """Escapes a string so it is valid within XML or XHTML."""
    return _XHTML_ESCAPE_RE.sub(lambda match: _XHTML_ESCAPE_DICT[match.group(0)],
                                to_basestring(value))


def xhtml_unescape(value):
    """Un-escapes an XML-escaped string."""
    return re.sub(r"&(#?)(\w+?);", _convert_entity, _unicode(value))



# I originally used the regex from
# http://daringfireball.net/2010/07/improved_regex_for_matching_urls
# but it gets all exponential on certain patterns (such as too many trailing
# dots), causing the regex matcher to never return.
# This regex should avoid those problems.
_URL_RE = re.compile(ur"""\b((?:([\w-]+):(/{1,3})|www[.])(?:(?:(?:[^\s&()]|&amp;|&quot;)*(?:[^!"#$%&'()*+,.:;<=>?@\[\]^`{|}~\s]))|(?:\((?:[^\s&()]|&amp;|&quot;)*\)))+)""")


def linkify(text, shorten=False, extra_params="",
            require_protocol=False, permitted_protocols=["http", "https"]):
    """Converts plain text into HTML with links.

    For example: ``linkify("Hello http://tornadoweb.org!")`` would return
    ``Hello <a href="http://tornadoweb.org">http://tornadoweb.org</a>!``

    Parameters:

    shorten: Long urls will be shortened for display.

    extra_params: Extra text to include in the link tag,
        e.g. linkify(text, extra_params='rel="nofollow" class="external"')

    require_protocol: Only linkify urls which include a protocol. If this is
        False, urls such as www.facebook.com will also be linkified.

    permitted_protocols: List (or set) of protocols which should be linkified,
        e.g. linkify(text, permitted_protocols=["http", "ftp", "mailto"]).
        It is very unsafe to include protocols such as "javascript".
    """
    if extra_params:
        extra_params = " " + extra_params.strip()

    def make_link(m):
        url = m.group(1)
        proto = m.group(2)
        if require_protocol and not proto:
            return url  # not protocol, no linkify

        if proto and proto not in permitted_protocols:
            return url  # bad protocol, no linkify

        href = m.group(1)
        if not proto:
            href = "http://" + href   # no proto specified, use http

        params = extra_params

        # clip long urls. max_len is just an approximation
        max_len = 30
        if shorten and len(url) > max_len:
            before_clip = url
            if proto:
                proto_len = len(proto) + 1 + len(m.group(3) or "")  # +1 for :
            else:
                proto_len = 0

            parts = url[proto_len:].split("/")
            if len(parts) > 1:
                # Grab the whole host part plus the first bit of the path
                # The path is usually not that interesting once shortened
                # (no more slug, etc), so it really just provides a little
                # extra indication of shortening.
                url = url[:proto_len] + parts[0] + "/" + \
                        parts[1][:8].split('?')[0].split('.')[0]

            if len(url) > max_len * 1.5:  # still too long
                url = url[:max_len]

            if url != before_clip:
                amp = url.rfind('&')
                # avoid splitting html char entities
                if amp > max_len - 5:
                    url = url[:amp]
                url += "..."

                if len(url) >= len(before_clip):
                    url = before_clip
                else:
                    # full url is visible on mouse-over (for those who don't
                    # have a status bar, such as Safari by default)
                    params += ' title="%s"' % href

        return u'<a href="%s"%s>%s</a>' % (href, params, url)

    # First HTML-escape so that our strings are all safe.
    # The regex is modified to avoid character entites other than &amp; so
    # that we won't pick up &quot;, etc.
    text = _unicode(xhtml_escape(text))
    #text = xhtml_escape(text)
    return _URL_RE.sub(make_link, text)


def render_comment_text(text):
    html = linkify(text, extra_params=' rel="nofollow"')
    html = re.sub('\n\n\n+', '\n\n', html)
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
        return JavascriptLexer()
    elif codesyntax == 'python':
        return PythonLexer()
    elif codesyntax == 'xml' or codesyntax == 'xml':
        return HtmlLexer()
    elif codesyntax == 'css':
        return CssLexer()
    elif codesyntax == 'sql':
        return SqlLexer()
    elif codesyntax:
        raise NotImplementedError(codesyntax)
    else:
        return TextLexer()

_codesyntax_regex = re.compile('```(python|cpp|javascript|xml|html|css|sql)')
_markdown_pre_regex = re.compile('```([^`]+)```')

def markdown_to_html(text, codesyntax):
#    print "PRE"
    def matcher(match):
        found = match.group()
        try:
            codesyntax = _codesyntax_regex.findall(found)[0]
        except IndexError:
            codesyntax = None
        #def codesyntax_finder(m):
        #    codesyntax = m.group()
        #    print "\tCODESYNTAX", repr(codesyntax)
        #    return '```'

        found = _codesyntax_regex.sub('```', found)
#        print "FOUND"
#        print repr(found)

        ##print repr(codesyntax)
#        print repr(found)
        if codesyntax:
            def highlighter(m):
 #               print "IN HERE"
 #               print "\t", repr(codesyntax)
 #               print "\t", repr(m.group())
 #               print "\t", repr('\n%s\n' % _highlight_it(m.group().strip(), codesyntax))
                lexer = _get_lexer(codesyntax)
                code = m.group().replace('```', '')
                return highlight(code, lexer, HtmlFormatter())
            found = _markdown_pre_regex.sub(highlighter, found)
        found = found.replace('```', '<pre>', 1)
        found = found.replace('```', '</pre>')
        print ""
        return found

    text = _markdown_pre_regex.sub(matcher, text)
    print repr(text)
    #print gfm(text)
    print "\n"
    html = markdown.markdown(gfm(text))
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
        if url.startswith('/') and _image_extension_regex.findall(url):
            url = '%s%s' % (prefix, url)
        return '%s="%s"' % (attr, url)

    return _SRC_regex.sub(matcher, text)
