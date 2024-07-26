#!/usr/bin/env python
import json
import random
import statistics
import sys
import time
from urllib.parse import urlparse

import requests
from pyquery import PyQuery

DEFAULT_CYCLES = 1000
DEFAULT_TOP_URLS = 200
DEFAULT_SLEEPTIME = 1.0
DEFAULT_REPORT_EVERY = 20


def get_urls(base_url, top_urls, exclude=set()):
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
        if len(urls) >= top_urls:
            break

    return urls


def get_sleeptime(default=DEFAULT_SLEEPTIME):
    try:
        with open("cdn-crawler-sleeptime") as f:
            return float(f.read().strip())
    except FileNotFoundError:
        return default


def stats(responses, last=100):
    def t(s):
        return ("\t" + s).ljust(20)

    def f(s):
        return "{:.2f}ms".format(s * 1000)

    values = responses
    if len(values) < 3:
        print("\tNot enough data")
        return
    if len(values) > last:
        print(t("COUNT"), len(values), "(but only using the last {})".format(last))
        values = values[-last:]
    else:
        print(t("COUNT"), len(values))

    if any([x["cache"] for x in values]):
        hits = len([x for x in values if x["cache"] == "HIT"])
        misses = len([x for x in values if x["cache"] == "MISS"])
        print(t("HIT RATIO"), "{:.1f}%".format(100 * hits / (hits + misses)))
        print(t("AVERAGE (all)"), f(statistics.mean([x["took"] for x in values])))
        print(t("MEDIAN (all)"), f(statistics.median([x["took"] for x in values])))
        try:
            print(
                t("AVERAGE (misses)"),
                f(statistics.mean([x["took"] for x in values if x["cache"] == "MISS"])),
            )
            print(
                t("MEDIAN (misses)"),
                f(
                    statistics.median(
                        [x["took"] for x in values if x["cache"] == "MISS"]
                    )
                ),
            )
            print(
                t("AVERAGE (hits)"),
                f(statistics.mean([x["took"] for x in values if x["cache"] == "HIT"])),
            )
            print(
                t("MEDIAN (hits)"),
                f(
                    statistics.median(
                        [x["took"] for x in values if x["cache"] == "HIT"]
                    )
                ),
            )
        except statistics.StatisticsError as exc:
            print(exc)
    else:
        hits = len([x for x in values if x["link"]])
        misses = len([x for x in values if not x["link"]])
        print(t("HIT RATIO"), "{:.1f}%".format(100 * hits / (hits + misses)))
        print(t("AVERAGE"), f(statistics.mean([x["took"] for x in values])))
        print(t("MEDIAN"), f(statistics.median([x["took"] for x in values])))

    with open("cdn-crawler-stats.json", "w") as f:
        json.dump(responses, f, indent=3)


def probe(url):
    t0 = time.time()
    r = requests.get(
        url,
        headers={
            "User-Agent": "cdn-crawler.py",
            "Accept-Encoding": "br, gzip, deflate",
        },
    )
    r.raise_for_status()
    t1 = time.time()
    print(
        urlparse(url).path.ljust(70),
        "{:.2f}ms".format((t1 - t0) * 1000),
        str(r.headers.get("x-cache")).ljust(6),
        "Nginx" if r.headers.get("link") and not r.headers.get("x-cache") else "",
    )
    return {
        "took": t1 - t0,
        "cache": r.headers.get("x-cache"),
        "link": r.headers.get("link"),
    }


def get_report_every(default):
    try:
        with open("cdn-crawler-report-every") as f:
            return int(f.read().strip())
    except FileNotFoundError:
        return default


def run(
    fresh_responses=False,
    cycles=DEFAULT_CYCLES,
    top_urls=DEFAULT_TOP_URLS,
    default_sleeptime=DEFAULT_SLEEPTIME,
    default_report_every=DEFAULT_REPORT_EVERY,
):
    responses = []
    if not fresh_responses:
        try:
            with open("cdn-crawler-stats.json") as f:
                responses = json.load(f)
                print("Continuing with {} responses".format(len(responses)))
        except FileNotFoundError:
            pass

    urls = get_urls("https://www.peterbe.com", top_urls)
    for _ in range(cycles):
        try:
            random.shuffle(urls)
            c = 0
            for url in urls:
                c += 1
                responses.append(probe(url))
                time.sleep(get_sleeptime())
                if not c % get_report_every(default_report_every):
                    stats(responses)
        except KeyboardInterrupt:
            print("One last time...")
            stats(responses)
            return 0

    print("One last time...")
    stats(responses)


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fresh-responses",
        action="store_true",
        default=False,
        help="Don't use history",
    )
    parser.add_argument(
        "--cycles",
        action="store",
        type=int,
        default=DEFAULT_CYCLES,
        help="Cycles to repeat (default {})".format(DEFAULT_CYCLES),
        nargs="?",
    )
    parser.add_argument(
        "--top-urls",
        action="store",
        type=int,
        default=DEFAULT_TOP_URLS,
        help="Top URLs to pick (default {})".format(DEFAULT_TOP_URLS),
        nargs="?",
    )
    parser.add_argument(
        "--default-sleeptime",
        action="store",
        type=float,
        default=DEFAULT_SLEEPTIME,
        help="Sleeptime between each probe (default {:.1f})".format(DEFAULT_SLEEPTIME),
        nargs="?",
    )
    parser.add_argument(
        "--default-report-every",
        action="store",
        type=int,
        default=DEFAULT_REPORT_EVERY,
        help="How often to display report (default {})".format(DEFAULT_REPORT_EVERY),
        nargs="?",
    )
    args = parser.parse_args()
    return run(**vars(args))


if __name__ == "__main__":
    sys.exit(main())
