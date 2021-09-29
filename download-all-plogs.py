#!/usr/bin/env python

import datetime
import json
import random
import time
from collections import defaultdict
from pathlib import Path

import requests
from pyquery import PyQuery


def get_urls(base_url, exclude=set()):
    urls = []
    if base_url.endswith("/"):
        base_url = base_url[:-1]
    doc = PyQuery(base_url + "/plog/")
    doc.make_links_absolute(base_url=base_url)
    for a in doc("dd a"):
        href = a.attrib["href"]
        if href in exclude:
            continue
        urls.append(href)

    doc = PyQuery(base_url + "/")
    doc.make_links_absolute(base_url=base_url)
    for a in doc("a"):
        try:
            href = a.attrib["href"]
        except KeyError:
            pass
        if not href.startswith(base_url):
            continue
        if href.endswith(".html") or href.endswith(".png"):
            continue
        if href.endswith("/search"):
            continue
        if href not in urls and href not in exclude:
            urls.append(href)
            urls.append(href)
            urls.append(href)

    url_start = base_url + "/p"
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
    x_caches = defaultdict(int)
    print(f"Found {len(urls):,} to enumerate")
    for i, url in enumerate(urls[:max]):
        # print(url.ljust(80))
        t0 = time.time()
        r = requests.get(url, headers=headers)
        t1 = time.time()
        r.raise_for_status()
        slow = bool(r.headers.get("X-Response-Time"))
        x_caches[r.headers["x-cache"]] += 1
        try:
            cache_control = r.headers["cache-control"]
        except KeyError:
            print("No 'Cache-Control' on", url)
            raise
        print(
            str(i + 1).ljust(3),
            url[:90].ljust(90),
            r.status_code,
            "\t",
            "%.3fs" % (t1 - t0),
            "slow!" if slow else "fast!",
            cache_control,
        )
        if slow:
            # It was so slow it had to generate in Django.
            time.sleep(sleeptime)
            slows += 1
        else:
            fasts += 1
        remember(url, r.status_code, t1 - t0, slow)

    if fasts or slows:
        print(f"{100 * fasts / (fasts + slows):.1f}% are fast")

    if x_caches:
        total = sum(x_caches.values())
        for key, value in x_caches.items():
            print(f"X-Cache: {key!r} {100 * value / total:.1f}%")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--max", default=100, help="Default 100")
    parser.add_argument("--sleeptime", default=1, help="Default 1")
    parser.add_argument(
        "--remember", action="store_true", default=False, help="Remember used last URLs"
    )
    parser.add_argument(
        "--linear",
        action="store_true",
        default=False,
        help="Start at the home page, each post there, then page 2 etc.",
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
        now = datetime.datetime.utcnow()
        state_file_name_prefix = Path(__file__).stem
        state_file_name = f"{state_file_name_prefix}.{now.strftime('%Y%m%d')}.json"
        state_file = Path("/tmp") / state_file_name

        # Delete all old remembering files stuck in the /tmp
        for other_state_file in Path("/tmp").glob(f"{state_file_name_prefix}.*"):
            if other_state_file != state_file:
                print(f"Deleting old state file {other_state_file}")
                other_state_file.unlink()

        try:
            with open(state_file) as f:
                for each in json.load(f):
                    exclude.add(each["url"])
            print(f"Loaded {len(exclude):,} URLs to exlude from {state_file}")
        except FileNotFoundError:
            with open(state_file, "w") as f:
                json.dump([], f)

    urls = get_urls(args.base_url, exclude=exclude)
    # urls = [x for x in urls if "040601" in x]
    if not args.linear:
        random.shuffle(urls)
    download(
        urls,
        args.base_url,
        max=int(args.max),
        sleeptime=float(args.sleeptime),
        state_file=state_file,
    )
