import datetime
import hashlib
import os
import re
import time
from urllib.parse import urlparse

from django import http
from django.conf import settings
from django.core.cache import cache
from django.utils.encoding import force_bytes

from peterbecom.base import fscache
from peterbecom.base.tasks import post_process_cached_html

max_age_re = re.compile(r"max-age=(\d+)")


def _is_too_new(fs_path, timeout=5):
    return os.path.isfile(fs_path) and os.stat(fs_path).st_mtime > time.time() - timeout


class FSCacheMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        fs_path = fscache.path_to_fs_path(request.path)
        if (
            settings.DEBUG
            and os.path.isfile(fs_path)
            and "nofscache" not in request.GET
        ):
            # If you don't have Nginx available, do what Nginx does but
            # in Django.
            cache_seconds = None
            if os.path.isfile(fs_path + ".cache_control"):
                with open(fs_path + ".cache_control") as f:
                    cache_seconds = int(f.read())
            if not fscache.too_old(fs_path, seconds=cache_seconds):
                print("Reusing FS cached file:", fs_path)
                response = http.HttpResponse()
                with open(fs_path, "rb") as f:
                    response.write(f.read())
                # exit early
                return response

        response = self.get_response(request)

        if fscache.cache_request(request, response) and not _is_too_new(fs_path):
            # if not fs_path:
            #     # exit early
            #     return response
            try:
                seconds = int(max_age_re.findall(response.get("Cache-Control"))[0])
            except TypeError:
                # exit early fi the cache-control isn't set
                return response
            if seconds > 60:
                metadata_text = "FSCache {}::{}::{}".format(
                    int(time.time()), seconds, datetime.datetime.utcnow()
                )
                # 'fs_path' is the path to the file, but its parent folder(s)
                # might need to be created.
                fscache.create_parents(fs_path)
                assert os.path.isdir(os.path.dirname(fs_path)), os.path.dirname(fs_path)
                raw_content = response.content.decode("utf-8")
                if not raw_content:
                    print(
                        "WARNING! Response content on {!r} was empty!".format(
                            request.path
                        )
                    )
                    # Bail on these weird ones
                    return response
                with open(fs_path, "w") as f:
                    f.write(raw_content)
                    if "text/html" in response["Content-Type"]:
                        f.write("\n<!-- {} -->\n".format(metadata_text))

                assert os.path.isfile(fs_path), fs_path
                if not os.stat(fs_path).st_size:
                    # Weird! The file does not appear have been written yet!
                    print(
                        "WARNING! fscache file {} on {!r} was empty!".format(
                            fs_path, request.path
                        )
                    )
                    os.remove(fs_path)
                    return response
                # assert os.stat(fs_path).st_size

                # This is a bit temporary
                # with open("/tmp/fscached2.log", "a") as f:
                #     f.write("{}\t{}\n".format(time.time(), fs_path))

                if os.path.isfile(fs_path + ".gz"):
                    print("Also, removed", fs_path + ".gz")  # TEMPORARY
                    os.remove(fs_path + ".gz")

                if os.path.isfile(fs_path + ".br"):
                    print("Also, removed", fs_path + ".br")  # TEMPORARY
                    os.remove(fs_path + ".br")

                with open(fs_path + ".metadata", "w") as f:
                    f.write(metadata_text)
                    f.write("\n")
                with open(fs_path + ".cache_control", "w") as f:
                    f.write(str(seconds))
                if "text/html" in response["Content-Type"]:
                    original_url = absolute_url = request.build_absolute_uri()
                    forwarded_host = request.headers.get("X-Forwarded-Host")
                    if forwarded_host and forwarded_host in settings.ALLOWED_HOSTS:
                        # Edit absolute_url using X-Forwarded-Host
                        absolute_url_parsed = urlparse(absolute_url)._replace(
                            netloc=forwarded_host
                        )
                        absolute_url = absolute_url_parsed.geturl()

                    if "\n" in absolute_url:
                        raise ValueError(
                            "An absolute URL with a newline in it ({!r})".format(
                                absolute_url
                            )
                        )

                    assert os.path.exists(fs_path), fs_path
                    cache_key = "post_process_cached_html:{}:{}".format(
                        hashlib.md5(force_bytes(fs_path)).hexdigest(),
                        hashlib.md5(force_bytes(absolute_url)).hexdigest(),
                    )
                    if not cache.get(cache_key):
                        cache.set(cache_key, True, 30)
                        post_process_cached_html(
                            fs_path,
                            absolute_url,
                            _start_time=time.time(),
                            original_url=original_url,
                        )

        return response


class StatsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        t0 = time.time()
        response = self.get_response(request)
        t1 = time.time()
        duration = t1 - t0
        response["X-Response-Time"] = int(duration * 1000)
        return response


class NoNewlineRequestPaths:
    """Any attempt to request a URL with a newline character in the path should
    cause a permanent redirect.

    The reason for this is we always want to at least try to give Nginx a chance
    to intercept the request to a file serve and if the URL contains a newline
    that can cause problems. In particular newline characters in file/folder names
    are hard to work with.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if "\n" in request.path:
            path = request.path.split("\n")[0]
            return http.HttpResponsePermanentRedirect(path)
        return self.get_response(request)
