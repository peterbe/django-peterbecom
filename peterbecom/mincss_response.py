import os
import time
import re
import logging
import hashlib
import codecs
import tempfile

# try:
#     import ujson as json
# except ImportError:
#     import json
from django.core.cache import cache

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


class DownloadCache:
    def __init__(self, default_expiry=500):
        self.default_expiry = default_expiry

    @staticmethod
    def _key(url):
        return 'downloadcache-{}'.format(
            hashlib.md5(url.encode('utf-8')).hexdigest()
        )

    def get(self, url):
        key = self._key(url)
        cached = cache.get(key)
        if cached is not None:
            return cached

    def set(self, url, payload):
        cache.set(self._key(url), payload, self.default_expiry)


download_cache = DownloadCache()


class CachedProcessor(Processor):

    # def __init__(self, *args, **kwargs):
    #     super(CachedProcessor, self).__init__(*args, **kwargs)
    #     self.cache_dir = os.path.join(
    #         tempfile.gettempdir(),
    #         'cached-mincss-processor'
    #     )
    #     if not os.path.isdir(self.cache_dir):
    #         os.mkdir(self.cache_dir)
    #     self.result = None
    #
    # def process_html(self, html, url):
    #     print('=' * 80)
    #     print(html[-60:])
    #     print('- ' * 40)
    #     hash_filename = hashlib.md5(
    #         (html + url).encode('utf-8')
    #     ).hexdigest() + '.json'
    #     hash_filepath = os.path.join(
    #         self.cache_dir,
    #         hash_filename
    #     )
    #     self.hash_filepath = hash_filepath
    #     print('self.hash_filepath', self.hash_filepath)
    #     if os.path.isfile(hash_filepath):
    #         print('\t', self.hash_filepath, 'exists!')
    #         age = time.time() - os.stat(hash_filepath).st_mtime
    #         print('\t', self.hash_filepath, 'AGE:', age)
    #         if age < 60 * 60 * 24 * 7:
    #             with open(hash_filepath, 'r') as f:
    #                 self.result = json.load(f)
    #                 print("CACHE HIT ON PROCESSED HTML {}".format(url))
    #                 return
    #         else:
    #             print("CACHE DELETE ON PROCESSED HTML {}".format(url))
    #             os.remove(hash_filepath)
    #
    #     print("CACHE MISS ON PROCESSED HTML {}".format(url))
    #     super(CachedProcessor, self).process_html(html, url)
    #
    # def process(self, *urls):
    #     if urls:
    #         raise NotImplementedError(urls)
    #     if self.result:
    #         # print "YAY! Reading from disk cache"
    #         self.inlines = [
    #             InlineResult(
    #                 x['line'],
    #                 x['url'],
    #                 x['before'],
    #                 x['after'],
    #             )
    #             for x in self.result['inlines']
    #         ]
    #         self.links = [
    #             LinkResult(
    #                 x['href'],
    #                 x['before'],
    #                 x['after'],
    #             )
    #             for x in self.result['links']
    #         ]
    #     else:
    #         super(CachedProcessor, self).process()
    #         with open(self.hash_filepath, 'w') as f:
    #             json.dump({
    #                 'links': [
    #                     {
    #                         'href': x.href,
    #                         'before': x.before,
    #                         'after': x.after,
    #                     }
    #                     for x in self.links
    #                 ],
    #                 'inlines': [
    #                     {
    #                         'line': x.line,
    #                         'url': x.url,
    #                         'before': x.before,
    #                         'after': x.after
    #                     }
    #                     for x in self.inlines
    #                 ],
    #             }, f)

    def download(self, url):
        downloaded = download_cache.get(url)
        if downloaded is None:
            downloaded = super(CachedProcessor, self).download(url)
            download_cache.set(url, downloaded)
        return downloaded


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
    print("SAVING MINCSSED HTML", type(html))
    with codecs.open(_mincssed_key(path), 'w', 'utf-8') as f:
        f.write(html)


def mincss_response(response, request):
    import warnings
    warnings.warn(
        "Use the post_process_cached_html() task instead.",
        DeprecationWarning,
    )
    if Processor is None or cssmin is None:
        logging.info("No mincss_response() possible")
        return response

    abs_uri = request.build_absolute_uri()
    if abs_uri.startswith('http://testserver'):
        return response

    html = response.content.decode('utf-8')
    html = mincss_html(html, abs_uri)
    response.content = html.encode('utf-8')
    return response


def mincss_html(html, abs_uri):
    t0 = time.time()
    p = CachedProcessor(
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

        def inline_remover(m):
            bail = m.group()
            if 'data-mincss="ignore"' in bail:
                return bail
            return ''

        html = _style_regex.sub(inline_remover, html)

    found_link_hrefs = [x.href for x in p.links]

    def link_remover(m):
        bail = m.group()
        for each in found_link_hrefs:
            if each in bail:
                return ''
        return bail

    html = _link_regex.sub(link_remover, html)

    _total_after = sum(len(x) for x in combined_css)
    combined_css = '\n'.join([cssmin.cssmin(x) for x in combined_css])

    try:
        combined_css = _clean_repeated_license_preambles(combined_css)
    except Exception as exception:
        print('Failure calling _clean_repeated_license_preambles: {}'.format(
            exception
        ))
    _total_after_min = len(combined_css)
    t2 = time.time()
    template = """
/*
Stats from using github.com/peterbe/mincss
------------------------------------------
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
        (_total_before - _total_after) / 1024.
    )
    stats_css = stats_css.replace(
        '*/',
        'Time to process:      %.2fms\n'
        'Time to post-process: %.2fms\n'
        '*/' % (
            (t1 - t0) * 1000,
            (t2 - t1) * 1000,
        )
    )
    combined_css = '{}\n{}'.format(
        stats_css.strip(),
        combined_css,
    )
    new_style = (
        '<style type="text/css">\n{}\n</style>'.format(combined_css)
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
    return html


def _clean_repeated_license_preambles(cssstring):
    # License preambles
    regex = re.compile(
        r'\/\*\!.*?\*\/\s+'
    )

    new_preamble = (
        '/* License for minified and inlined CSS originally belongs '
        'to Semantic UI. See individual files in '
        'https://github.com/peterbe/django-peterbecom/tree/master/peterbecom/base/static/css '  # noqa
        '*/'
    )
    cssstring = regex.sub('', cssstring)
    return new_preamble + '\n' + cssstring
