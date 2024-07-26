import concurrent.futures

import requests
from django.conf import settings
from requests.exceptions import ReadTimeout


def get_x_cache(url, no_brotli=False):
    endpoints = settings.HTTP_RELAY_ENDPOINTS
    assert endpoints
    session = requests.Session()

    # It must be a full URL
    assert "://" in url and url.startswith("http"), url

    results = {}
    futures = {}
    with concurrent.futures.ThreadPoolExecutor() as executor:
        for use_brotli in (True, False):
            if no_brotli and use_brotli:
                continue
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

            if result["error"]:
                results[endpoint] = {
                    "error": result["error"],
                }
            else:
                results[endpoint] = {
                    "took": result["meta"]["took"],
                    "elapsed": result["response"]["elapsed"],
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
    if r.status_code == 400:
        print(r.text)
        raise ValueError(f"Bad parameters posted to {endpoint}: {r.json()}")
    r.raise_for_status()
    return r.json()
