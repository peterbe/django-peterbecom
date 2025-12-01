import re
from json.decoder import JSONDecodeError
from urllib.parse import urlparse

from django.conf import settings
from django.core.cache import cache
from django.shortcuts import redirect

from peterbecom.base.utils import requests_retry_session


class NotOKError(Exception):
    """when the response is not 200 OK"""


class RedirectNeeded(Exception):
    """when a redirect is needed"""


class NonJSONError(Exception):
    """when the response is not JSON as expected"""


DEFAULT_REQUEST_RETRIES = 2


def get_song(id, request_retries=DEFAULT_REQUEST_RETRIES):
    cache_key = f"lyrics_song_{id}"
    res = cache.get(cache_key)

    if not res:
        print("SONGCACHE", cache_key, "MISS")
        remote_url = f"{settings.LYRICS_REMOTE}/api/song/{id}"
        response = requests_retry_session(retries=request_retries).get(remote_url)
        if response.status_code != 200:
            raise NotOKError(response.status_code)
            # return http.JsonResponse(
            #     {"error": "Unexpected proxy response code"}, status=response.status_code
            # )

        if len(response.history) == 1 and response.history[0].status_code == 301:
            path = urlparse(response.history[0].headers.get("Location")).path
            new_url = f"/plog/blogitem-040601-1{path}"
            raise RedirectNeeded(new_url)
            # return redirect(new_url)

        try:
            res = response.json()
        except JSONDecodeError:
            if "<!DOCTYPE html>" in response.text:
                print(f"HTML WHEN EXPECTING JSON! {remote_url}")

                path = urlparse(response.url).path
                if path.startswith("/song/") and re.findall(r"/\d+$", path):
                    new_url = f"/plog/blogitem-040601-1{path}"
                    # raw_query_string = request.META.get("QUERY_STRING", "")
                    # if raw_query_string:
                    #     new_url += f"?{raw_query_string}"
                    return redirect(new_url)
                raise RedirectNeeded(new_url)

            print(f"WARNING: JSONDecodeError ({remote_url})", response.text)
            raise NonJSONError()
            # return http.JsonResponse(
            #     {"error": "Unexpected non-JSON error on fetching song"},
            #     status=response.status_code,
            # )

        # Could bump this to 3 months when we're confident it won't
        # bloat the Redis storage.
        cache.set(cache_key, res, timeout=60 * 60 * 24 * 7 * 8)
    else:
        print("SONGCACHE", cache_key, "HIT")

    return res
