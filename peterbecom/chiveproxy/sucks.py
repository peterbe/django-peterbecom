import hashlib
import re

import pyquery

from django.core.cache import cache
from django.conf import settings

from . import puppeteer


def make_it_more_iso(datestr):
    return re.sub(r"\b(\d)\b", r"0\1", datestr)


def get_cards():
    base = "https://thechive.com/"
    doc = pyquery.PyQuery(base)

    for slot in doc("div.slot").items():
        for a in slot("a.card-img-link").items():
            href = a.attr("href")
            if not href.startswith(base):
                continue
            for img in a("img.card-thumb").items():
                img = img.attr("src")
                break
            else:
                continue
            break
        else:
            continue

        assert img.startswith("https"), img
        for a in slot("h3.post-title a").items():
            text = a.text().replace("\xa0", " ").strip()
            if text.lower().endswith("(video)"):
                continue
            if text.lower().endswith("(vote)"):
                continue
            break
        else:
            continue

        date = None
        human_time = None
        for time_ in slot("time[datetime]").items():
            date = time_.attr("datetime")
            date = make_it_more_iso(date)
            human_time = time_.text()  # Not needed?
            break

        uri = hashlib.md5(href.encode("utf-8")).hexdigest()[:8]
        yield {
            "url": href,
            "uri": uri,
            "text": text,
            "img": img,
            "date": date,
            "human_time": human_time,
        }


def get_card(url):
    assert url.startswith("https://thechive.com"), url

    puppeteer_cache_key = "puppeteer_sucks:{}".format(url[-50:])

    # This cache is really just for local development.
    html = cache.get(puppeteer_cache_key)
    if html is None:
        print("Sucking", url)
        html = puppeteer.suck(url)
        print("SUCKED", url)
        if html:
            cache.set(puppeteer_cache_key, html, 60)
    else:
        print("No need sucking", url, "(cached)")
    doc = pyquery.PyQuery(html)

    for h1 in doc("h1#post-title").items():
        text = h1.text()
        text = text.replace("\xa0", " ").strip()
        break
    else:
        return

    date = None
    for time_ in doc("header.article-header time[datetime]").items():
        date = time_.attr("datetime")
        break

    pictures = []
    # for figure in doc("div.gallery figure.gallery-item").items():
    for figure in doc("figure.gallery-item").items():
        caption = []
        gifsrc = None
        src = None
        for p in figure("figcaption.gallery-caption p").items():
            caption.append(p.text())
        for img in figure("img.attachment-gallery-item-full").items():
            src = img.attr("src")
            gifsrc = img.attr("data-gifsrc")
            break
        else:
            for img in figure("img.attachment-gallery-item-hires").items():
                src = img.attr("src")
                break
        if not src:
            # Happens sometimes when it's just a bunch of Twitter quotes.
            if settings.DEBUG:
                raise Exception("No src on {}".format(url))
            print("NO PICTURES figuree", figure)
            continue

        src = src.replace("http://", "https://")
        # assert src.startswith("https://"), src
        if gifsrc:
            gifsrc = gifsrc.replace("http://", "https://")
            # assert gifsrc.startswith("https://")

        pictures.append({"img": src, "gifsrc": gifsrc, "caption": "\n".join(caption)})

    return {"text": text, "pictures": pictures, "date": date}
