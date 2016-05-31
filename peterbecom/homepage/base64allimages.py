import re
import logging
import base64
import urlparse
import urllib
from django.contrib.sites.requests import RequestSite
from django.conf import settings


_img_regex = re.compile(
    '(<img.*?src=(["\'])([^"\']+)(["\']).*?>)',
    re.DOTALL | re.M
)


def post_process_response(response, request):
    current_url = request.build_absolute_uri().split('?')[0]
    base_url = 'https://' if request.is_secure() else 'http://'
    base_url += RequestSite(request).domain
    current_url = urlparse.urljoin(base_url, request.path)
    this_domain = urlparse.urlparse(current_url).netloc

    def image_replacer(match):
        bail = match.group()
        whole, deli, src, deli = match.groups()
        if src.startswith('//'):
            if request.is_secure():
                abs_src = 'https:' + src
            else:
                abs_src = 'http:' + src
        else:
            abs_src = urlparse.urljoin(current_url, src)
        if urlparse.urlparse(abs_src).netloc != this_domain:
            if settings.STATIC_URL and settings.STATIC_URL in abs_src:
                pass
            else:
                return bail

        img_response = urllib.urlopen(abs_src)
        ct = img_response.headers['content-type']
        if img_response.getcode() >= 300:
            logging.warning(
               "Unable to download %s (code: %s)",
               abs_src, img_response.getcode()
            )
            return bail

        img_content = img_response.read()
        new_src = (
            'data:%s;base64,%s' %
            (ct, base64.encodestring(img_content).replace('\n', ''))
        )
        old_src = 'src=%s%s%s' % (deli, src, deli)
        new_src = 'src=%s%s%s' % (deli, new_src, deli)
        new_src += ' data-orig-src=%s%s%s' % (deli, src, deli)
        return bail.replace(old_src, new_src)

    response.content = _img_regex.sub(image_replacer, response.content)
    return response
