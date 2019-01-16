import codecs
import hashlib
import logging
import os
import re
import tempfile
import time
from urllib.parse import urlparse

import delegator
import requests
from django.conf import settings
from django.core.cache import cache
from mincss.processor import Processor
from pyquery import PyQuery

try:
    import cssmin
except ImportError:
    logging.warning("Unable to import cssmin", exc_info=True)
    cssmin = None

logger = logging.getLogger("mincss-response")

_style_regex = re.compile("<style.*?</style>", re.M | re.DOTALL)
_link_regex = re.compile("<link.*?>", re.M | re.DOTALL)

# A hack to use files instead of memcache
cache_save_dir = os.path.join(tempfile.gettempdir(), "mincssed_responses")
if not os.path.isdir(cache_save_dir):
    os.mkdir(cache_save_dir)


class DownloadCache:
    def __init__(self, default_expiry=500):
        self.default_expiry = default_expiry

    @staticmethod
    def _key(url):
        return "downloadcache-{}".format(hashlib.md5(url.encode("utf-8")).hexdigest())

    def get(self, url):
        key = self._key(url)
        cached = cache.get(key)
        if cached is not None:
            return cached

    def set(self, url, payload):
        cache.set(self._key(url), payload, self.default_expiry)


download_cache = DownloadCache()


class CachedProcessor(Processor):
    def download(self, url):
        downloaded = download_cache.get(url)
        if downloaded is None:
            downloaded = super(CachedProcessor, self).download(url)
            download_cache.set(url, downloaded)
        return downloaded


def _mincssed_key(path):
    filename = path.replace("/", "_") + ".html"
    return os.path.join(cache_save_dir, filename)


def _get_mincssed_html(path):
    filepath = _mincssed_key(path)
    try:
        with codecs.open(filepath, "r", "utf-8") as f:
            return f.read(), time.time() - os.stat(filepath).st_mtime
    except IOError:
        return None, None


def _save_mincssed_html(path, html):
    print("SAVING MINCSSED HTML", type(html))
    with codecs.open(_mincssed_key(path), "w", "utf-8") as f:
        f.write(html)


def mincss_html(html, abs_uri):
    # print("PING: {}".format(
    #     requests.get(settings.MINIMALCSS_SERVER_URL + '/').status_code
    # ))
    t0 = time.time()
    r = requests.post(
        settings.MINIMALCSS_SERVER_URL + "/minimize",
        json={"url": abs_uri},
        timeout=settings.MINIMALCSS_TIMEOUT_SECONDS,
    )
    if r.status_code != 200:
        print(
            "WARNING! "
            "{} status code trying to minimize {}".format(r.status_code, abs_uri)
        )
        return

    result = r.json()["result"]
    t1 = time.time()

    found_link_hrefs = list(result["stylesheetContents"].keys())

    if 0 and abs_uri.endswith("/plog/blogitem-040601-1"):
        template = (
            '<link rel="preload" href="{url}" as="style" media="delayed">\n'
            '<noscript><link rel="stylesheet" href="{url}"></noscript>'
        )
    else:
        template = (
            '<link rel="preload" href="{url}" as="style" '
            "onload=\"this.onload=null;this.rel='stylesheet'\">\n"
            '<noscript><link rel="stylesheet" href="{url}"></noscript>'
        )

    def equal_uris(uri1, uri2):
        # If any one of them is relative, compare their paths
        if uri1.startswith("//"):
            uri1 = "https:" + uri1
        if uri2.startswith("//"):
            uri2 = "https:" + uri2

        if "://" in uri1:
            uri1 = urlparse(uri1).path
        if "://" in uri2:
            uri2 = urlparse(uri2).path

        return uri1 == uri2

    def link_remover(m):
        bail = m.group()
        try:
            href = re.findall(r'href="([^"]+)"', bail)[0]
        except IndexError:
            return bail
        for each in found_link_hrefs:
            # 'each' is always a full absolute URL, but the
            # link tag might be something like "/static/foo.css"
            # print('\tEACH {!r}'.format(each))
            if equal_uris(each, href):
                return template.format(url=each)
        return bail

    html = _link_regex.sub(link_remover, html)
    #
    # _total_after = sum(len(x) for x in combined_css)
    # combined_css = '\n'.join([cssmin.cssmin(x) for x in combined_css])
    combined_css = result["finalCss"]
    _total_after = len(combined_css)

    try:
        combined_css = _clean_repeated_license_preambles(combined_css)
    except Exception as exception:
        print("Failure calling _clean_repeated_license_preambles: {}".format(exception))
    _total_after_min = len(combined_css)

    # t2 = time.time()

    style_tags_regex = re.compile(r"<style>(.*?)</style>", re.DOTALL)

    def style_rewriter(match):
        whole = match.group()
        css = match.groups()[0]
        try:
            new_css = _clean_with_csso(css)
            return whole.replace(css, new_css)
        except Exception as exception:
            raise
            print("Failure calling _clean_with_csso: {}".format(exception))
            return whole

    html = style_tags_regex.sub(style_rewriter, html)

    _requests_before = len(result["stylesheetContents"])
    _total_before = sum(len(v) for v in result["stylesheetContents"].values())

    t3 = time.time()
    template = """
/*
Stats from using github.com/peterbe/minimalcss
----------------------------------------------
Requests:             %s (now: 0)
Before:               %.fKb
After:                %.fKb
After (minified):     %.fKb
Saving:               %.fKb
*/"""
    stats_css = template % (
        _requests_before,
        _total_before / 1024.,
        _total_after / 1024.,
        _total_after_min / 1024.,
        (_total_before - _total_after) / 1024.,
    )
    stats_css = stats_css.replace(
        "*/",
        "Time to process:      %.2fms\n"
        "Time to post-process: %.2fms\n"
        "*/" % ((t1 - t0) * 1000, (t3 - t1) * 1000),
    )
    combined_css = "{}\n{}".format(stats_css.strip(), combined_css)
    new_style = "<style>\n{}\n</style>".format(combined_css)
    html = html.replace("</head>", new_style + "\n</head>")

    logger.info("Took %.2fms to process with minimalcss" % ((t1 - t0) * 1000,))
    # logger.info('Took %.2fms to post-process remaining CSS' % (
    #     (t2 - t1) * 1000,
    # ))
    return html


def _clean_repeated_license_preambles(cssstring):
    regex = re.compile(r"\/\*\!.*?\*\/\s+", re.DOTALL)
    new_preamble = (
        "/*! License for minified and inlined CSS originally belongs "
        "to Semantic UI. See individual files in "
        "https://github.com/peterbe/django-peterbecom/tree/master/peterbecom/base/static/css "  # noqa
        "*/"
    )
    cssstring = regex.sub("", cssstring)
    return new_preamble + "\n" + cssstring


def _clean_with_csso(cssstring):
    with tempfile.TemporaryDirectory() as dir_:
        input_fn = os.path.join(dir_, "input.css")
        output_fn = os.path.join(dir_, "output.css")
        with open(input_fn, "w") as f:
            f.write(cssstring)
        command = "node {} -i {} -o {}".format(
            settings.CSSO_CLI_BINARY, input_fn, output_fn
        )
        r = delegator.run(command)
        if r.return_code:
            raise RuntimeError(
                "Return code: {}\tError: {}".format(r.return_code, r.err)
            )
        with open(output_fn) as f:
            output = f.read()

    return output


def has_been_css_minified(html):
    doc = PyQuery(html)
    for link in doc('link[rel="preload"]').items():
        if link.attr("href") and link.attr("href").endswith(".css"):
            # Second test, does it have a big fat style text:
            for style in doc("style").items():
                length = len(style.text())
                if length > 5000:
                    return True

    return False
