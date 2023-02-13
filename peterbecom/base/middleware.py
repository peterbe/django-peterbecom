import re
import time

from django import http

max_age_re = re.compile(r"max-age=(\d+)")


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
