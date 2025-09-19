import re
import time
import uuid

from django import http
from django.conf import settings

from peterbecom.base.batch_events import create_event_later
from peterbecom.base.utils import fake_ip_address

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


class PublicAPIPageviewsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        t0 = time.time()
        response = self.get_response(request)
        t1 = time.time()
        duration = t1 - t0
        if request.path.startswith("/api/v1/"):
            data = {
                "duration": duration,
                "method": request.method,
            }
            query_string = request.META.get("QUERY_STRING", "")
            meta = {
                "path": request.path,
                "query_string": query_string,
                "request_url": request.build_absolute_uri(),
            }

            ip_address = request.headers.get("x-forwarded-for") or request.META.get(
                "REMOTE_ADDR"
            )
            if (
                ip_address == "127.0.0.1"
                and settings.DEBUG
                and request.get_host().endswith("127.0.0.1:8000")
            ):
                ip_address = fake_ip_address(str(time.time()))
            if ip_address:
                meta["ip_address"] = ip_address

            url = request.path
            if query_string:
                url += f"?{query_string}"

            try:
                create_event_later(
                    type="publicapi-pageview",
                    uuid=str(uuid.uuid4()),
                    url=url,
                    meta=meta,
                    data=data,
                )
            except Exception as err:
                if settings.DEBUG:
                    raise err
                print(f"WARNING! Unable to save 'publicapi-pageview': {err}")

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
