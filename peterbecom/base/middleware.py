import datetime
import hashlib
import re
import time
from pathlib import Path
from urllib.parse import urlparse

from django import http
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import MiddlewareNotUsed
from django.utils.encoding import force_bytes

from peterbecom.base import fscache
from peterbecom.base.tasks import post_process_cached_html

max_age_re = re.compile(r"max-age=(\d+)")


def _is_too_new(fs_path: Path, timeout=5):
    return fs_path.exists() and fs_path.stat().st_mtime > time.time() - timeout


class FSCacheMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

        if not settings.FSCACHE_ROOT:
            raise MiddlewareNotUsed

    def __call__(self, request):
        fs_path = fscache.path_to_fs_path(request.path)
        if settings.DEBUG and fs_path.exists() and "nofscache" not in request.GET:
            # If you don't have Nginx available, do what Nginx does but
            # in Django.
            cache_seconds = None
            cc_path = Path(str(fs_path) + ".cache_control")
            if cc_path.exists():
                with open(cc_path) as f:
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
                # exit early if the cache-control isn't set
                return response
            if seconds > 60:
                metadata_text = f"FSCache {int(time.time())}::{seconds}::{datetime.datetime.utcnow()}"
                # 'fs_path' is the path to the file, but its parent folder(s)
                # might need to be created.
                fscache.create_parents(fs_path)
                assert fs_path.parent.is_dir(), fs_path.parent
                raw_content = response.content.decode("utf-8")
                if not raw_content:
                    print(f"WARNING! Response content on {request.path!r} was empty!")
                    # Bail on these weird ones
                    return response
                with open(fs_path, "w") as f:
                    f.write(raw_content)
                    if "text/html" in response["Content-Type"]:
                        f.write("\n<!-- {} -->\n".format(metadata_text))

                # assert os.path.isfile(fs_path), fs_path
                assert fs_path.exists(), fs_path
                if not fs_path.stat().st_size:
                    # Weird! The file does not appear have been written yet!
                    print(
                        f"WARNING! fscache file {fs_path} on {request.path!r} was empty!"
                    )
                    fs_path.unlink()
                    return response

                fs_path_gz = Path(str(fs_path) + ".gz")
                if fs_path_gz.exists():
                    print(f"Also, removed {fs_path_gz}")
                    fs_path_gz.unlink()

                fs_path_br = Path(str(fs_path) + ".br")
                if fs_path_br.exists():
                    print(f"Also, removed {fs_path_br}")
                    fs_path_br.unlink()

                fs_path_metadata = Path(str(fs_path) + ".metadata")
                with open(fs_path_metadata, "w") as f:
                    f.write(metadata_text)
                    f.write("\n")

                fs_path_cc = Path(str(fs_path) + ".cache_control")
                with open(fs_path_cc, "w") as f:
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
                    elif not forwarded_host:
                        # When you open something like
                        # https://www-origin.peterbe.com/plog/page with minimalcss
                        # it will be done with `X-Forwarded-Host: www.peterbe.com`
                        # but consequent XHR requests within won't keep that
                        # X-Forwarded-Host header. So we'll have to fix that manually.
                        absolute_url_parsed = urlparse(absolute_url)
                        if absolute_url_parsed.netloc in settings.ORIGIN_TO_HOST:
                            absolute_url_parsed = absolute_url_parsed._replace(
                                netloc=settings.ORIGIN_TO_HOST[
                                    absolute_url_parsed.netloc
                                ]
                            )
                            absolute_url = absolute_url_parsed.geturl()

                    if "\n" in absolute_url:
                        raise ValueError(
                            "An absolute URL with a newline in it ({!r})".format(
                                absolute_url
                            )
                        )

                    # assert os.path.exists(fs_path), fs_path
                    assert fs_path.exists(), fs_path
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
