import inspect
from urllib.parse import urlparse

import keycdn
import requests
from requests.exceptions import RequestException
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from requests.exceptions import RetryError

from peterbecom.base.utils import requests_retry_session
from peterbecom.base.models import CDNPurgeURL


def get_stack_signature():
    frames = []
    for frame in inspect.stack()[1:]:
        if (
            "site-packages" in frame.filename
            or "Cellar" in frame.filename
            or "python3.5" in frame.filename
        ):
            continue
        split = frame.filename.split("/")
        frames.append("{}:{}".format("/".join(split[-3:]), frame.lineno))
    return ";".join(frames)


def get_requests_retry_session():
    # return requests_retry_session(status_forcelist=(500, 502, 504, 429))
    return requests_retry_session(status_forcelist=(500, 502, 504))


class BrokenKeyCDNConfig(Exception):
    """When the response from KeyCDN zone config isn't right."""


def get_cdn_config(api=None):
    if not api:
        api = keycdn.Api(settings.KEYCDN_API_KEY)
        # Whilst waiting for
        # https://github.com/keycdn/python-keycdn-api/commit/9165aa164f4a837f8419044ae64d26f5f65d0857
        # we'll just have to set it afterwards.
        api.session = get_requests_retry_session()

    cache_key = "cdn_config:{}".format(settings.KEYCDN_ZONE_ID)
    r = cache.get(cache_key)
    if r is None:
        with open("/tmp/get_cdn_config.log", "a") as f:
            f.write("{}\t{}\n".format(timezone.now(), get_stack_signature()))
        r = api.get("zones/{}.json".format(settings.KEYCDN_ZONE_ID))
        cache.set(cache_key, r, 60 * 60)
    return r


def purge_cdn_urls(urls, api=None):
    if settings.USE_NGINX_BYPASS:
        # Note! This Nginx trick will not just purge the proxy_cache, it will
        # immediately trigger a refetch.
        x_cache_headers = []
        for url in urls:
            if "://" not in url:
                url = settings.NGINX_BYPASS_BASEURL + url
            try:
                r = requests.get(url, headers={"secret-header": "true"})
                r.raise_for_status()
                x_cache_headers.append(
                    {"url": url, "x-cache": r.headers.get("x-cache")}
                )
                print("X-CACHE-HEADERS", x_cache_headers)
                CDNPurgeURL.succeeded(urls)
            except Exception:
                CDNPurgeURL.failed(urls)
                raise
        return {"all_urls": urls, "result": x_cache_headers}

    if not keycdn_zone_check():
        print("WARNING! Unable to use KeyCDN API at the moment :(")
        return

    if not api:
        api = keycdn.Api(settings.KEYCDN_API_KEY)
        api.session = get_requests_retry_session()
    config = get_cdn_config(api)
    # See https://www.keycdn.com/api#purge-zone-url
    try:
        cachebr = config["data"]["zone"]["cachebr"] == "enabled"
    except KeyError:
        raise BrokenKeyCDNConfig("Config={!r}".format(config))
    all_urls = []

    # For KeyCDN we need to do some transformations. Our URLs are different
    # from the KeyCDN "URLs". When we make this transformation, maintain a map
    # *back* to the original URLs as they're known to us.
    original_urls = {}

    for absolute_url in urls:
        url = settings.KEYCDN_ZONE_URL + urlparse(absolute_url).path
        all_urls.append(url)
        original_urls[url] = absolute_url
        if cachebr:
            all_urls.append(url + "br")
            original_urls[url + "br"] = absolute_url

    # Make absolutely sure nothing's repeated.
    all_all_urls = sorted(list(set(all_urls)))

    def get_original_urls(cdn_urls):
        original = set()
        for url in cdn_urls:
            original.add(original_urls[url])
        return original

    # Break it up into lists of 100
    def chunks(l, n):
        # For item i in a range that is a length of l,
        for i in range(0, len(l), n):
            # Create an index range for l of n items:
            yield l[i : i + n]

    for all_urls in chunks(all_all_urls, 100):
        call = "zones/purgeurl/{}.json".format(settings.KEYCDN_ZONE_ID)
        params = {"urls": all_urls}

        with open("/tmp/purge_cdn_urls.log", "a") as f:
            f.write(
                "{}\t{!r}\t{}\n".format(timezone.now(), all_urls, get_stack_signature())
            )
        try:
            r = api.delete(call, params)
            CDNPurgeURL.succeeded(get_original_urls(all_urls))
        except Exception:
            CDNPurgeURL.failed(get_original_urls(all_urls))
            raise
        print(
            "SENT CDN PURGE FOR: {!r}\tORIGINAL URLS: {!r}\tRESULT: {}".format(
                all_urls, urls, r
            )
        )
    return {"result": r, "all_urls": all_all_urls}


def keycdn_zone_check(refresh=False):
    """KeyCDN's API is unpredictable unfortunately and the python-keycdn-api
    a bit flawed. For example, if you try to use it when it's not working
    you get JSONDecodeErrors. And it's currently not possible to do retries.
    So this is an attempt at a backoff-able check but done manually.
    """

    cache_key = "keycdn_check:{}".format(settings.KEYCDN_ZONE_ID)
    works = cache.get(cache_key)
    if works is None or refresh:
        with open("/tmp/keycdn_zone_check.log", "a") as f:
            f.write("{}\t{}\n".format(timezone.now(), get_stack_signature()))
        session = get_requests_retry_session()
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
        except RequestException as exception:
            print(
                "WARNING! RequestException error checking KeyCDN Zone: {}".format(
                    exception
                )
            )
            works = False
        cache.set(cache_key, works, 60)

    return works
