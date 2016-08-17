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
        'User-Agent': 'download-all-plogs.py/requests 1.0',
    }
    for url in urls[:max]:
        print url.ljust(80),
        t0 = time.time()
        r = requests.get(url, headers=headers)
        t1 = time.time()
        print r.status_code, '\t', '%.2fs' % (t1 - t0)
        time.sleep(sleeptime)

    # also download a bunch of pages of the home page
    url_start = 'https://www.peterbe.com/?page='
    for i in range(2, max):
        url = url_start + str(i)
        print url.ljust(80),
        t0 = time.time()
        r = requests.get(url, headers=headers)
        t1 = time.time()
        print r.status_code, '\t', '%.2fs' % (t1 - t0)
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
