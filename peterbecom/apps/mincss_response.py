import os
import time
import re
import logging
import hashlib
import codecs
import tempfile

from django.core.cache import cache
from django.utils import timezone

from mincss.processor import Processor
try:
    import cssmin
except ImportError:
    logging.warning("Unable to import cssmin", exc_info=True)
    cssmin = None

logger = logging.getLogger('mincss-response')

_style_regex = re.compile('<style.*?</style>', re.M | re.DOTALL)
_link_regex = re.compile('<link.*?>', re.M | re.DOTALL)

# A hack to use files instead of memcache
cache_save_dir = os.path.join(tempfile.gettempdir(), 'mincssed_responses')
if not os.path.isdir(cache_save_dir):
    os.mkdir(cache_save_dir)


def mincss_response(response, request):
    html, age = _get_mincssed_html(request.path)

    if html is not None:
        if age > 60 * 60:
            age_human = '%.1f hours' % (age / 3600.0)
        elif age > 60:
            age_human = '%.1f minutes' % (age / 60.0)
        else:
            age_human = '%d seconds' % (age, )
        print "BUT!! It existed as a file!", age_human

    t0 = time.time()
    r = _mincss_response(response, request)
    t1 = time.time()
    print "Running mincss_response for: %s (Took %.3fs) %s" % (
        request.path,
        t1 - t0,
        timezone.now().isoformat()
    )
    return r


def _mincssed_key(path):
    filename = path.replace('/', '_') + '.html'
    return os.path.join(cache_save_dir, filename)


def _get_mincssed_html(path):
    filepath = _mincssed_key(path)
    try:
        with codecs.open(filepath, 'r', 'utf-8') as f:
            return f.read(), time.time() - os.stat(filepath).st_mtime
    except IOError:
        return None, None


def _save_mincssed_html(path, html):
    with codecs.open(_mincssed_key(path), 'w', 'utf-8') as f:
        f.write(html)


def _mincss_response(response, request):
    if Processor is None or cssmin is None:
        logging.info("No mincss_response() possible")
        return response

    abs_uri = request.build_absolute_uri()
    if abs_uri.startswith('http://testserver'):
        return response

    lock_key = 'lock:' + hashlib.md5(request.path).hexdigest()
    if cache.get(lock_key):
        # we're actively busy prepping this one
        print "Bailing because mincss_response is already busy for: %s" % (
            request.path,
        )
        return response
    cache.set(lock_key, True, 200)
    print "Starting to mincss for: %s" % (
        request.path,
    )
    html = unicode(response.content, 'utf-8')
    t0 = time.time()
    p = Processor(
        preserve_remote_urls=True,
    )
    p.process_html(html, abs_uri)
    p.process()
    t1 = time.time()
    combined_css = []
    _total_before = 0
    _requests_before = 0

    for link in p.links:
        _total_before += len(link.before)
        _requests_before += 1
        combined_css.append(link.after)

    for inline in p.inlines:
        _total_before += len(inline.before)
        combined_css.append(inline.after)

    if p.inlines:
        html = _style_regex.sub('', html)
    found_link_hrefs = [x.href for x in p.links]

    def link_remover(m):
        bail = m.group()
        for each in found_link_hrefs:
            if each in bail:
                return ''
        return bail

    html = _link_regex.sub(link_remover, html)

    _total_after = sum(len(x) for x in combined_css)
    combined_css = [cssmin.cssmin(x) for x in combined_css]
    _total_after_min = sum(len(x) for x in combined_css)
    t2 = time.time()
    template = """
/*
Stats about using github.com/peterbe/mincss
-------------------------------------------
Requests:         %s (now: 0)
Before:           %.fKb
After:            %.fKb
After (minified): %.fKb
Saving:           %.fKb
*/"""
    stats_css = template % (
        _requests_before,
        _total_before / 1024.,
        _total_after / 1024.,
        _total_after_min / 1024.,
        (_total_before - _total_after) / 1024.
    )
    combined_css.insert(0, stats_css)
    new_style = (
        '<style type="text/css">\n%s\n</style>' %
        ('\n'.join(combined_css)).strip()
    )
    html = html.replace(
        '</head>',
        new_style + '\n</head>'
    )
    logger.info('Took %.2fms to process with mincss' % (
        (t1 - t0) * 1000,
    ))
    logger.info('Took %.2fms to post-process remaining CSS' % (
        (t2 - t1) * 1000,
    ))

    _save_mincssed_html(request.path, html)
    response.content = html.encode('utf-8')
    return response
