import random
import re
import time
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
GET_SONG_TTL_SECONDS = 60 * 60 * 24 * 7 * 8


def get_song(id, request_retries=DEFAULT_REQUEST_RETRIES, refresh_cache=False):
    cache_key = f"lyrics_song_{id}"
    res = None if refresh_cache else cache.get(cache_key)

    log_prefix = "REFRESH-SONGCACHE" if refresh_cache else "SONGCACHE"

    if not res:
        print(log_prefix, cache_key, "MISS", f"retries={request_retries}")
        remote_url = f"{settings.LYRICS_REMOTE}/api/song/{id}"
        response = requests_retry_session(retries=request_retries).get(remote_url)
        if response.status_code != 200:
            raise NotOKError(response.status_code)

        if len(response.history) == 1 and response.history[0].status_code == 301:
            path = urlparse(response.history[0].headers.get("Location")).path
            new_url = f"/plog/blogitem-040601-1{path}"
            raise RedirectNeeded(new_url)

        try:
            res = response.json()
        except JSONDecodeError:
            if "<!DOCTYPE html>" in response.text:
                print(f"HTML WHEN EXPECTING JSON! {remote_url}")

                path = urlparse(response.url).path
                if path.startswith("/song/") and re.findall(r"/\d+$", path):
                    new_url = f"/plog/blogitem-040601-1{path}"
                    return redirect(new_url)
                raise RedirectNeeded(new_url)

            print(f"WARNING: JSONDecodeError ({remote_url})", response.text)
            raise NonJSONError()

        cache.set(cache_key, res, timeout=GET_SONG_TTL_SECONDS)
    else:
        print(log_prefix, cache_key, "HIT")

    return res


def refresh_song_cache(
    max_refresh_count=10, random_sample_size=1_000, sleep_time=1, min_percent_left=20
):
    def s_print(seconds):
        if seconds > 60 * 60 * 24 * 7:
            return f"{seconds / (60 * 60 * 24 * 7):.1f} weeks"
        if seconds > 60 * 60 * 24:
            return f"{seconds / (60 * 60 * 24):.1f} days"
        if seconds > 60 * 60:
            return f"{seconds / (60 * 60):.1f} hours"
        if seconds > 60:
            return f"{seconds / 60:.1f} minutes"
        return f"{seconds:.1f} seconds"

    keys = cache.keys("lyrics_song_*")
    print(len(keys), "keys")

    print("TOTAL/MAX TTL:", s_print(GET_SONG_TTL_SECONDS))

    key_age = []
    for key in random.sample(keys, min(random_sample_size, len(keys))):
        for song_id in re.findall(r"lyrics_song_(\d+)", key):
            age_left = cache.ttl(key)
            key_age.append((age_left, key, song_id))
    key_age.sort()
    refresh_ids = []
    for age_left, key, song_id in key_age:
        percent_left = 100 * age_left / GET_SONG_TTL_SECONDS

        print(key.ljust(20), s_print(age_left), f"{percent_left:.1f}% left")
        if percent_left < min_percent_left:
            refresh_ids.append((age_left, key, song_id))
            if len(refresh_ids) >= max_refresh_count:
                print("Reached max_refresh_count of possible candidates")
                break

    print(len(refresh_ids), "up for refresh")
    if len(refresh_ids) > max_refresh_count:
        print(f"Max {max_refresh_count} to refresh this time.")

    for i, (age, _, song_id) in enumerate(refresh_ids[:max_refresh_count]):
        print(i + 1, "Refreshing song_id", song_id)
        song = get_song(int(song_id), refresh_cache=True, request_retries=0)
        print(
            "Refreshed",
            repr(song["song"]["name"]),
            "by",
            repr(song["song"]["artist"]["name"]),
        )
        time.sleep(sleep_time)
        print()
