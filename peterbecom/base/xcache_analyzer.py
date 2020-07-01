import concurrent.futures

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
        for use_brotli in (True, False):
            for endpoint in endpoints:
                futures[
                    executor.submit(
                        check_endpoint, session, endpoint, url, use_brotli, 5
                    )
                ] = f"{endpoint}{':brotli' if use_brotli else ''}"
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
                "x_cache": iget(result["response"]["headers"], "x-cache"),
            }

    # Dicts are sorted, but not when they trickle in from a thread pool.
    sorted_results = {}
    for key in sorted(results):
        sorted_results[key] = results[key]

    return sorted_results


def iget(map, key, default=None):
    for k in map:
        if k.lower() == key.lower():
            return map[k]
    return default


def check_endpoint(session, endpoint, url, use_brotli, timeout):
    json_data = {"url": url, "timeout": timeout, "nobody": True}
    if use_brotli:
        json_data["headers"] = {"Accept-Encoding": "br"}
    r = session.post(endpoint, json=json_data)
    r.raise_for_status()
    return r.json()
