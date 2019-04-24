from urllib.parse import urlparse

from django.core.cache import cache
from django.conf import settings
from keycdn import keycdn  # https://github.com/keycdn/python-keycdn-api/issues/4


def get_cdn_config(api=None):
    api = api or keycdn.Api(settings.KEYCDN_API_KEY)
    cache_key = "cdn_config:{}".format(settings.KEYCDN_ZONE_ID)
    r = cache.get(cache_key)
    if r is None:
        r = api.get("zones/{}.json".format(settings.KEYCDN_ZONE_ID))
        cache.set(cache_key, r, 60 * 5)
    return r


def purge_cdn_urls(urls):
    api = keycdn.Api(settings.KEYCDN_API_KEY)
    config = get_cdn_config(api)
    # See https://www.keycdn.com/api#purge-zone-url
    cachebr = config["data"]["zone"]["cachebr"] == "enabled"
    all_urls = []
    for absolute_url in urls:
        url = settings.KEYCDN_HOST + urlparse(absolute_url).path
        all_urls.append(url)
        if cachebr:
            all_urls.append(url + "br")
    call = "zones/purgeurl/{}.json".format(settings.KEYCDN_ZONE_ID)
    params = {"urls": all_urls}

    r = api.delete(call, params)
    print("SENT CDN PURGE FOR", all_urls, "RESULT:", r)
    return {"result": r, "all_urls": all_urls}
