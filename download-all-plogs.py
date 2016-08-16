#!/usr/bin/env python

import time
import random

import requests
from pyquery import PyQuery


def get_urls():
    doc = PyQuery('https://www.peterbe.com/plog/')
    doc.make_links_absolute(base_url='https://www.peterbe.com')
    urls = []
    for a in doc('dd a'):
        urls.append(a.attrib['href'])
    return urls


def download(urls, max=100, sleeptime=1):
    headers = {
        'User-Agent': 'download-all-plots.py/requests 1.0',
    }
    for url in urls[:max]:
        print url,
        print requests.get(url, headers=headers).status_code
        time.sleep(sleeptime)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", default=100)
    parser.add_argument("--sleeptime", default=1)
    args = parser.parse_args()

    urls = get_urls()
    random.shuffle(urls)
    download(
        urls,
        max=int(args.max),
        sleeptime=float(args.sleeptime),
    )
