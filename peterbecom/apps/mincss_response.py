from django.conf import settings

import re
from mincss.processor import Processor
try:
    import cssmin
except ImportError:
    logging.warning("Unable to import cssmin", exc_info=True)
    cssmin = None

_style_regex = re.compile('<style.*?</style>', re.M | re.DOTALL)
_link_regex = re.compile('<link.*?>', re.M | re.DOTALL)


def mincss_response(response, request):
    if Processor is None or cssmin is None:
        logging.info("No mincss_response() possible")
        return response

    abs_uri = request.build_absolute_uri()
    if abs_uri.startswith('http://testserver'):
        return response

    html = unicode(response.content, 'utf-8')
    p = Processor(
        preserve_remote_urls=True,
    )
    p.process_html(html, abs_uri)
    p.process()
    combined_css = []
    _total_before = 0
    _requests_before = 0
    for link in p.links:
        _total_before += len(link.before)
        _requests_before += 1
        #combined_css.append('/* %s */' % link.href)
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

    stats_css = (
"""
/*
Stats about using github.com/peterbe/mincss
-------------------------------------------
Requests:         %s (now: 0)
Before:           %.fKb
After:            %.fKb
After (minified): %.fKb
Saving:           %.fKb
*/"""
        % (_requests_before,
           _total_before / 1024.,
           _total_after / 1024.,
           _total_after_min / 1024.,
           (_total_before - _total_after) / 1024.)

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
    response.content = html.encode('utf-8')
    return response
