import concurrent.futures
from urllib.parse import urlencode

import requests
from requests.exceptions import ReadTimeout

from django.conf import settings


def get_x_cache(url):
    endpoints = settings.HTTP_RELAY_ENDPOINTS
    assert endpoints
    session = requests.Session()

    results = {}
    futures = {}
    with concurrent.futures.ThreadPoolExecutor() as executor:
        for endpoint in endpoints:
            futures[
                executor.submit(check_endpoint, session, endpoint, url, 5)
            ] = endpoint
        for future in concurrent.futures.as_completed(futures):
            endpoint = futures[future]
            try:
                result = future.result()
            except ReadTimeout as exception:
                results[endpoint] = {"took": None, "error": str(exception)}
                continue

            results[endpoint] = {
                "took": result["meta"]["took"],
                "error": None,
                "status": result["response"]["status_code"],
                "x-cache": iget(result["response"]["headers"], "x-cache"),
            }

    return results


def iget(map, key, default=None):
    for k in map:
        if k.lower() == key.lower():
            return map[k]
    return default


def check_endpoint(session, endpoint, url, timeout):
    r = session.get(endpoint + "?" + urlencode({"url": url, "timeout": timeout}))
    r.raise_for_status()
    return r.json()
