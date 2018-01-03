import os
import datetime
import re
import time

from django import http
from django.conf import settings

from peterbecom.base import fscache
from peterbecom.base.tasks import post_process_cached_html


max_age_re = re.compile('max-age=(\d+)')


class FSCacheMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        fs_path = fscache.path_to_fs_path(request.path)
        if (
            settings.DEBUG and
            os.path.isfile(fs_path) and
            'nofscache' not in request.GET
        ):
            # If you don't have Nginx available, do what Nginx does but
            # in Django.
            cache_seconds = None
            if os.path.isfile(fs_path + '.cache_control'):
                with open(fs_path + '.cache_control') as f:
                    cache_seconds = int(f.read())
            if not fscache.too_old(fs_path, seconds=cache_seconds):
                print("Reusing FS cached file:", fs_path)
                response = http.HttpResponse()
                with open(fs_path, 'rb') as f:
                    response.write(f.read())
                # exit early
                return response

        response = self.get_response(request)

        if fscache.cache_request(request, response):
            # if not fs_path:
            #     # exit early
            #     return response
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
                # 'fs_path' is the path to the file, but its parent folder(s)
                # might need to be created.
                fscache.create_parents(fs_path)
                assert os.path.isdir(os.path.dirname(fs_path))
                with open(fs_path, 'w') as f:
                    f.write(response.content.decode('utf-8'))
                    if 'text/html' in response['Content-Type']:
                        f.write('\n<!-- {} -->\n'.format(metadata_text))
                with open(fs_path + '.metadata', 'w') as f:
                    f.write(metadata_text)
                    f.write('\n')
                with open(fs_path + '.cache_control', 'w') as f:
                    f.write(str(seconds))
                if 'text/html' in response['Content-Type']:
                    absolute_url = request.build_absolute_uri()
                    # If you're in docker, the right hostname is actually
                    # 'web', not 'localhost'.
                    absolute_url = absolute_url.replace(
                        '//localhost:8000',
                        '//web:8000'
                    )
                    absolute_url = absolute_url.replace(
                        '//peterbecom.dev',
                        '//web:8000'
                    )
                    print("FS_PATH", fs_path, os.path.exists(fs_path))
                    assert os.path.exists(fs_path), fs_path
                    post_process_cached_html.delay(
                        fs_path,
                        absolute_url,
                    )

        return response
