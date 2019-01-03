import hashlib
import re

import pyquery

from django.conf import settings


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
    doc = pyquery.PyQuery(url)

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
    for figure in doc("div.gallery figure.gallery-item").items():
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
            continue
        assert src.startswith("https://"), src
        if gifsrc:
            assert gifsrc.startswith("https://")

        pictures.append({"img": src, "gifsrc": gifsrc, "caption": "\n".join(caption)})

    return {"text": text, "pictures": pictures, "date": date}
