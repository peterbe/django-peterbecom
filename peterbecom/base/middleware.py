import codecs
import datetime
import re
import time


from django.conf import settings
from peterbecom.base.fscache import path_to_fs_path

max_age_re = re.compile('max-age=(\d+)')


class FSCacheMiddleware(object):

    def process_response(self, request, response):
        if not settings.FSCACHE_ROOT:
            # bail if it hasn't been set up
            return response
        if (
            request.method == 'GET' and
            request.path != '/' and
            response.status_code == 200 and
            not request.META.get('QUERY_STRING') and
            not request.user.is_authenticated() and
            # XXX TODO: Support JSON and xml
            'text/html' in response['Content-Type']
        ):
            fs_path = path_to_fs_path(request.path)
            try:
                seconds = int(
                    max_age_re.findall(response.get('Cache-Control'))[0]
                )
            except TypeError:
                # exit early fi the cache-control isn't set
                return response
            if seconds > 60:
                metadata_text = 'FSCache {}::{}::{}'.format(
                    int(time.time()),
                    seconds,
                    datetime.datetime.utcnow()
                )
                # Proceed only if it's a long'ish time to be cached
                with codecs.open(fs_path, 'w', response.charset) as f:
                    f.write(unicode(response.content, response.charset))
                    if 'text/html' in response['Content-Type']:
                        f.write('\n<!-- {} -->'.format(metadata_text))
                with open(fs_path + '.metadata', 'w') as f:
                    f.write(metadata_text)
                    f.write('\n')
        return response
