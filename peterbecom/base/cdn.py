from urllib.parse import urlparse

import keycdn
import requests
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from requests.exceptions import RetryError

from peterbecom.base.utils import requests_retry_session


def get_cdn_config(api=None):
    api = api or keycdn.Api(settings.KEYCDN_API_KEY)
    cache_key = "cdn_config:{}".format(settings.KEYCDN_ZONE_ID)
    r = cache.get(cache_key)
    if r is None:
        r = api.get("zones/{}.json".format(settings.KEYCDN_ZONE_ID))
        cache.set(cache_key, r, 60 * 15)
    return r


def purge_cdn_urls(urls, api=None):
    if settings.USE_NGINX_BYPASS:
        # Note! This Nginx trick will not just purge the proxy_cache, it will
        # immediately trigger a refetch.
        x_cache_headers = []
        for url in urls:
            if "://" not in url:
                url = settings.NGINX_BYPASS_BASEURL + url
            r = requests.get(url, headers={"secret-header": "true"})
            r.raise_for_status()
            x_cache_headers.append({"url": url, "x-cache": r.headers.get("x-cache")})
        print("X-CACHE-HEADERS", x_cache_headers)
        return {"all_urls": urls, "result": x_cache_headers}

    if not keycdn_zone_check():
        print("WARNING! Unable to use KeyCDN API at the moment :(")
        return

    api = api or keycdn.Api(settings.KEYCDN_API_KEY)
    config = get_cdn_config(api)
    # See https://www.keycdn.com/api#purge-zone-url
    cachebr = config["data"]["zone"]["cachebr"] == "enabled"
    all_urls = []
    for absolute_url in urls:
        url = settings.KEYCDN_ZONE_URL + urlparse(absolute_url).path
        all_urls.append(url)
        if cachebr:
            all_urls.append(url + "br")
    call = "zones/purgeurl/{}.json".format(settings.KEYCDN_ZONE_ID)
    params = {"urls": all_urls}

    r = api.delete(call, params)
    print("SENT CDN PURGE FOR", all_urls, "RESULT:", r)
    return {"result": r, "all_urls": all_urls}


def keycdn_zone_check(refresh=False):
    """KeyCDN's API is unpredictable unfortunately and the python-keycdn-api
    a bit flawed. For example, if you try to use it when it's not working
    you get JSONDecodeErrors. And it's currently not possible to do retries.
    So this is an attempt at a backoff-able check but done manually.
    """

    cache_key = "keycdn_check:{}".format(settings.KEYCDN_ZONE_ID)
    works = cache.get(cache_key)
    if works is None or refresh:
        session = requests_retry_session()
        try:
            response = session.get(
                "https://api.keycdn.com/"
                + "zones/{}.json".format(settings.KEYCDN_ZONE_ID),
                auth=(settings.KEYCDN_API_KEY, ""),
            )
            response.raise_for_status()
            works = timezone.now()
        except RetryError as exception:
            print("WARNING! Retry error checking KeyCDN Zone: {}".format(exception))
            works = False

        cache.set(cache_key, works, 60)

    return works
