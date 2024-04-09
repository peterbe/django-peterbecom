import markdown
import time
import datetime
import json
import functools
import hashlib
import re
from urllib.parse import urlencode, urlparse
import subprocess
from html import escape

import bleach
import requests

# https://github.com/vzhou842/profanity-check is probably better but it requires
# scikit-learn or whatever it's called.
from profanity import profanity
from requests.exceptions import ConnectionError
import zope.structuredtext
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
    html = bleach.clean(text, tags=[])

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

        # If the href was written like this: [a-z]+.[A-Z][a-z]+ it could simply
        # be a missing space when separating the sentences.
        # Also, if the found href was never found in the text, it really can't
        # be a valid URL. I.e. "Here is a sentence.It starts with" would find
        # 'http://sentence.It` but the input was without the http:// part.
        if re.search(r"[a-z]+\.[A-Z][a-z]+", href) and href not in text:
            # Suspect!
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

    def match(s):
        _, inner = s.groups()
        new_inner = inner
        new_inner = new_inner.replace("&gt;", ">").replace("&lt;", "<")
        lines = new_inner.splitlines()
        lines = [re.sub(r"^\s", "", x) for x in lines]
        new_inner = "\n".join(lines)
        new_inner = hylite_wrapper(new_inner, codesyntax or "shell")

        return new_inner

    return _regex.sub(match, rendered)


def hylite_wrapper(code, language):
    aliases = {"emacslisp": "lisp"}
    language = aliases.get(language) or language
    command = settings.HYLITE_COMMAND.split()
    assert language
    command.extend(["--language", language, "--wrapped"])
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=settings.HYLITE_DIRECTORY,
    )
    process.stdin.write(code)
    output, error = process.communicate()

    # Check the return code to see if the command was successful
    return_code = process.returncode
    if return_code != 0:
        raise Exception(error or output)

    return output


_codesyntax_regex = re.compile(r"```(\w+)")
_markdown_pre_regex = re.compile(r"(```(.*?)```)", re.M | re.DOTALL)


def markdown_to_html(text):
    def matcher(match):
        found = match.group()
        try:
            codesyntax = _codesyntax_regex.findall(found)[0]
        except IndexError:
            codesyntax = None
        found = _codesyntax_regex.sub("```", found)
        if codesyntax:

            def highlighter(m):
                code = m.group().replace("```", "")
                highlighted = hylite_wrapper(code, codesyntax)
                return highlighted

            found = _markdown_pre_regex.sub(highlighter, found)
        else:

            def highlighter(m):
                meat = m.groups()[1]
                return f"<pre>{escape(meat.strip())}</pre>"

            found = _markdown_pre_regex.sub(highlighter, found)
        return found

    text = _markdown_pre_regex.sub(matcher, text)
    html = markdown.markdown(gfm(text), extensions=["markdown.extensions.tables"])
    html = html.replace("<pre><span></span>", "<pre>")

    # Markdown leaves a strange whitespace before the end of the paragraph.
    # Manually clean that up.
    html = re.sub(r"[ ]+</p>", "</p>", html)

    return html


_SRC_regex = re.compile(r'(src|href)="([^"]+)"')
_image_extension_regex = re.compile(r"\.(png|jpg|jpeg|gif)$", re.I)


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


def get_comment_page(blogcomment):
    root_comment = blogcomment
    while root_comment.parent_id:
        root_comment = root_comment.parent

    model = blogcomment._meta.model
    qs = model.objects.filter(blogitem=blogcomment.blogitem, parent__isnull=True)
    ids = list(qs.order_by("-add_date").values_list("id", flat=True))
    per_page = settings.MAX_RECENT_COMMENTS
    for i in range(settings.MAX_BLOGCOMMENT_PAGES):
        sub_list = ids[i * per_page : (i + 1) * per_page]
        if root_comment.id in sub_list:
            return i + 1
    return 1


def rate_blog_comment(comment):
    result = {"good": {}, "bad": {}}

    MAX_LENGTH = 800

    # Exclude comments that have links in them unless the links are to
    # www.peterbe.com or songsear.ch.
    OK_DOMAINS = ["www.peterbe.com", "songsear.ch"]
    links = []

    page = 1
    if comment.blogitem.oid == "blogitem-040601-1":
        # Special conditions apply!
        # If the comment in question is on anything beyond the first page,
        # it lowers the bar significantly.
        page = get_comment_page(comment)
        if page > 1:
            OK_DOMAINS.append("youtu.be")
            OK_DOMAINS.append("www.youtube.com")
            MAX_LENGTH = 2000
            result["good"]["deep"] = "on page {}".format(page)
        elif comment.parent:
            # It's a reply!
            # If it's really short and has no bad, it should be fine as is!
            if len(comment.comment) < 400 and comment.comment.count("\n") <= 2:
                result["good"]["shortreply"] = "special and reply and short"

    def find_links(attrs, new=False):
        href = attrs[(None, "href")]
        p = urlparse(href)
        if p.netloc not in OK_DOMAINS:
            links.append(href)

    linker = Linker(callbacks=[find_links])
    linker.linkify(comment.comment)

    if links:
        result["bad"]["links"] = links

    if len(comment.comment) > MAX_LENGTH:
        result["bad"]["length"] = ">{} characters".format(MAX_LENGTH)

    if profanity.contains_profanity(comment.comment):
        result["bad"]["profanity"] = "contains profanities"

    for keyword in ("spell cast", "whatsapp", "+1("):
        if keyword in comment.comment.lower():
            if result["bad"].get("spam_keywords"):
                result["bad"]["spam_keywords"] = (
                    f"{keyword!r}, ${result['bad']['spam_keywords']}"
                )
            else:
                result["bad"]["spam_keywords"] = f"{keyword!r}"

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


def get_blogcomment_slice(count_comments, page):
    slice_m, slice_n = (
        max(0, count_comments - settings.MAX_RECENT_COMMENTS),
        count_comments,
    )
    slice_m -= (page - 1) * settings.MAX_RECENT_COMMENTS
    slice_m = max(0, slice_m)
    slice_n -= (page - 1) * settings.MAX_RECENT_COMMENTS

    return (slice_m, slice_n)
