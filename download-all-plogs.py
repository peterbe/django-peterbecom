#!/usr/bin/env python

import time
import random

import requests
from pyquery import PyQuery


def get_urls(base_url):
    if base_url.endswith('/'):
        base_url = base_url[:-1]
    doc = PyQuery(base_url + '/plog/')
    doc.make_links_absolute(base_url=base_url)
    urls = []
    for a in doc('dd a'):
        urls.append(a.attrib['href'])
    return urls


def download(urls, base_url, max=100, sleeptime=1):
    headers = {
        'User-Agent': 'download-all-plogs.py/requests 1.0',
    }
    for url in urls[:max]:
        print(url.ljust(80))
        t0 = time.time()
        r = requests.get(url, headers=headers)
        t1 = time.time()
        print(r.status_code, '\t', '%.2fs' % (t1 - t0))
        time.sleep(sleeptime)

    # also download a bunch of pages of the home page
    url_start = base_url + '?page='
    for i in range(2, 10):
        url = url_start + str(i)
        print(url.ljust(80))
        t0 = time.time()
        r = requests.get(url, headers=headers)
        t1 = time.time()
        print(r.status_code, '\t', '%.2fs' % (t1 - t0))
        time.sleep(sleeptime)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", default=100, help="Default 100")
    parser.add_argument("--sleeptime", default=1, help="Default 1")
    parser.add_argument(
        "--base-url",
        default='https://www.peterbe.com',
        help="Default https://www.peterbe.com"
    )
    args = parser.parse_args()

    urls = get_urls(args.base_url)
    random.shuffle(urls)
    download(
        urls,
        args.base_url,
        max=int(args.max),
        sleeptime=float(args.sleeptime),
    )
