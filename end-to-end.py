import os
import re
import pyquery
import xmltodict
import requests


BASE_URL = os.environ.get("BASE_URL", "https://peterbecom.local")
print("Testing against:", BASE_URL)


def get(url, **options):
    if "://" not in url:
        url = BASE_URL + url
    options.setdefault("verify", "peterbecom.local" not in url)
    return requests.get(url, **options)


def test_rss_feeds():
    r = get("/rss.xml")
    assert r.status_code == 200
    assert "public" in r.headers["cache-control"]
    assert re.findall(r"max-age=\d+", r.headers["cache-control"])
    assert r.headers["content-encoding"] == "gzip"
    parsed = xmltodict.parse(r.text)
    items = parsed["rss"]["channel"]["item"]
    titles = [x["title"] for x in items]
    assert titles

    # Do with with a query string
    r = get("/rss.xml?oc=Django")
    assert r.status_code == 200
    assert "public" in r.headers["cache-control"]
    assert re.findall(r"max-age=\d+", r.headers["cache-control"])
    assert r.headers["content-encoding"] == "gzip"
    parsed = xmltodict.parse(r.text)
    django_items = parsed["rss"]["channel"]["item"]
    django_titles = [x["title"] for x in django_items]
    assert django_titles != titles

    r = get("/oc-Django/rss.xml")
    assert r.status_code == 200
    assert "public" in r.headers["cache-control"]
    assert re.findall(r"max-age=\d+", r.headers["cache-control"])
    assert r.headers["content-encoding"] == "gzip"
    parsed = xmltodict.parse(r.text)
    django_items2 = parsed["rss"]["channel"]["item"]
    django_titles2 = [x["title"] for x in django_items2]
    assert django_titles == django_titles2


def test_homepage():
    r = get("/")
    assert r.status_code == 200
    assert re.findall(r"max-age=\d+", r.headers["cache-control"])
    assert "public" in r.headers["cache-control"]
    assert r.headers["content-encoding"] == "gzip"
    assert r.headers["content-type"].lower() == "text/html; charset=utf-8".lower()
    # Commented out because it doesn't work when testing locally with http://
    # assert r.headers["Strict-Transport-Security"]
    print(r.headers.items())
    assert r.headers["x-cache"]


def test_search():
    r = get("/search?q=python")
    assert r.status_code == 200
    # assert re.findall(r"max-age=\d+", r.headers["cache-control"])
    # assert "public" in r.headers["cache-control"]
    doc = pyquery.PyQuery(r.text.strip())
    header, = doc("h1").items()
    print(header)
