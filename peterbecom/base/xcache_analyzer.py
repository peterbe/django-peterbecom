import re
import time
import concurrent.futures

import requests
from requests.exceptions import ReadTimeout
from pyquery import PyQuery


URL = "https://tools.keycdn.com/queries/perf-query.php"
GET_URL = "https://tools.keycdn.com/performance"


def get_x_cache(url):
    session = requests.Session()
    r = session.get(GET_URL, timeout=3)
    r.raise_for_status()
    token = re.findall(r"token=([a-f0-9]+)", r.text)[0]
    assert token, "no token found"

    locations = re.findall(r'var location = "(\w+)";', r.text)
    assert locations, "no locations found"

    results = {}
    futures = {}
    with concurrent.futures.ThreadPoolExecutor() as executor:
        for location in locations:
            futures[
                executor.submit(_post_x_cache, session, token, url, location)
            ] = location
        for future in concurrent.futures.as_completed(futures):
            location = futures[future]
            try:
                results[location] = future.result()
            except (ReadTimeout, EmptyHeaders) as exception:
                results[location] = {"took": None, "error": str(exception)}

    return results


class EmptyHeaders(Exception):
    pass


def _post_x_cache(session, token, url, location):
    t0 = time.time()
    r = session.post(
        URL, data={"location": location, "url": url, "token": token}, timeout=10
    )
    t1 = time.time()
    print(url, "FORM", location, "TOOK", t1 - t0)
    r.raise_for_status()
    results = r.json()
    if not results["headers"]:
        raise EmptyHeaders(results)
    doc = PyQuery(results["result"])
    data = {}
    for i, td in enumerate(doc("td").items()):
        if i == 6:
            try:
                data["ttfb"] = float(
                    list(td("span.badge-success").items())[0]
                    .text()
                    .replace("ms", "")
                    .strip()
                )
            except IndexError:
                if "ms" in td.text():
                    data["ttfb"] = float(td.text().replace("ms", "").strip())
                else:
                    data["ttfb"] = 1000 * float(td.text().replace("s", "").strip())

    doc = PyQuery(results["headers"])
    key = None
    for dt_dd in doc("dt,dd").items():
        if key is None:
            key = dt_dd.text().strip()
        else:
            value = dt_dd.text().strip()
            if key == "x-cache":
                data[key] = value
            key = None

    return data
