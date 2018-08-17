#!/usr/bin/env python

import datetime
import json
import os
import random
import time

import requests
from pyquery import PyQuery


def get_urls(base_url, exclude=set()):
    if base_url.endswith("/"):
        base_url = base_url[:-1]
    doc = PyQuery(base_url + "/plog/")
    doc.make_links_absolute(base_url=base_url)
    urls = []
    for a in doc("dd a"):
        href = a.attrib["href"]
        if href in exclude:
            # print("EXCLUDE", href)
            continue
        urls.append(href)

    doc = PyQuery(base_url + "/")
    doc.make_links_absolute(base_url=base_url)
    for a in doc("p a"):
        href = a.attrib["href"]
        if href.startswith(base_url) and "oc-" in href:
            if href not in urls:
                if href in exclude:
                    # print("EXCLUDE", href)
                    continue
                urls.append(href)
                for i in range(5):
                    urls.append(href)
    url_start = base_url + "/?page="
    for i in range(2, 10):
        url = url_start + str(i)
        if url in exclude:
            continue
        urls.append(url)
    return urls


def download(urls, base_url, max=100, sleeptime=1, state_file=None):
    def remember(url, status_code, t, slow):
        if state_file is None:
            return
        with open(state_file) as f:
            state = json.load(f)
        state.append({"url": url, "status": status_code, "time": t, "slow": slow})
        with open(state_file, "w") as f:
            json.dump(state, f, indent=2, sort_keys=True)

    headers = {"User-Agent": "download-all-plogs.py/requests 1.0"}
    fasts = slows = 0
    for i, url in enumerate(urls[:max]):
        # print(url.ljust(80))
        t0 = time.time()
        r = requests.get(url, headers=headers)
        t1 = time.time()
        slow = bool(r.headers.get("X-Response-Time"))
        print(
            str(i + 1).ljust(3),
            url[:100].ljust(100),
            r.status_code,
            "\t",
            "%.3fs" % (t1 - t0),
            "slow!" if slow else "fast!",
        )
        if slow:
            # It was so slow it had to generate in Django.
            time.sleep(sleeptime)
            slows += 1
        else:
            fasts += 1
        remember(url, r.status_code, t1 - t0, slow)

    if fasts or slow:
        print("{:.1f}%".format(100 * fasts / (fasts + slows)), "are fast")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--max", default=100, help="Default 100")
    parser.add_argument("--sleeptime", default=1, help="Default 1")
    parser.add_argument(
        "--remember", action="store_true", default=False, help="Remember used last URLs"
    )
    parser.add_argument(
        "--base-url",
        default="https://www.peterbe.com",
        help="Default https://www.peterbe.com",
    )
    args = parser.parse_args()

    exclude = set()
    state_file = None
    if args.remember:
        # What we did we do last time (in the last 24h)?
        state_file = os.path.join(
            "/tmp",
            os.path.splitext(os.path.basename(__file__))[0]
            + ".{}.json".format(datetime.datetime.now().strftime("%Y%m%d")),
        )
        try:
            with open(state_file) as f:
                for each in json.load(f):
                    exclude.add(each["url"])
        except FileNotFoundError:
            with open(state_file, "w") as f:
                json.dump([], f)
    urls = get_urls(args.base_url, exclude=exclude)
    random.shuffle(urls)
    download(
        urls,
        args.base_url,
        max=int(args.max),
        sleeptime=float(args.sleeptime),
        state_file=state_file,
    )
