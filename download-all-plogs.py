#!/usr/bin/env python

import time
import random

import requests
from pyquery import PyQuery


def get_urls(base_url):
    if base_url.endswith("/"):
        base_url = base_url[:-1]
    doc = PyQuery(base_url + "/plog/")
    doc.make_links_absolute(base_url=base_url)
    urls = []
    for a in doc("dd a"):
        urls.append(a.attrib["href"])

    doc = PyQuery(base_url + "/")
    doc.make_links_absolute(base_url=base_url)
    for a in doc("p a"):
        href = a.attrib["href"]
        if href.startswith(base_url) and "oc-" in href:
            if href not in urls:
                urls.append(href)
                for i in range(5):
                    urls.append(href)
    return urls


def download(urls, base_url, max=100, sleeptime=1):
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

    # also download a bunch of pages of the home page
    url_start = base_url + "/?page="
    for i in range(2, 6):
        url = url_start + str(i)
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
            time.sleep(sleeptime)
            slows += 1
        else:
            fasts += 1

    if fasts or slow:
        print("{.:1f}% are fast".format(100 * fasts / (fasts + slows)))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--max", default=100, help="Default 100")
    parser.add_argument("--sleeptime", default=1, help="Default 1")
    parser.add_argument(
        "--base-url",
        default="https://www.peterbe.com",
        help="Default https://www.peterbe.com",
    )
    args = parser.parse_args()

    urls = get_urls(args.base_url)
    random.shuffle(urls)
    download(urls, args.base_url, max=int(args.max), sleeptime=float(args.sleeptime))
