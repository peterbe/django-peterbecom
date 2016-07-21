import codecs
import datetime
import re
import time

from peterbecom.base.fscache import path_to_fs_path, cache_request

max_age_re = re.compile('max-age=(\d+)')


class FSCacheMiddleware(object):

    def process_response(self, request, response):
        if cache_request(request, response):
            fs_path = path_to_fs_path(request.path)
            if not fs_path:
                # exit early
                return response
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
