import hashlib
import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import pyquery
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from . import html_getter


def make_it_more_iso(datestr):
    return re.sub(r"\b(\d)\b", r"0\1", datestr)


def get_cards(limit=None, debug=False, html=None):
    def log(*args):
        if debug:
            print(f"SUCKS ({timezone.now()}):", *args)

    base = "https://thechive.com/"
    if html is None:
        html = html_getter.suck(base, debug=debug)
        assert html, base
        if debug:
            with open("/tmp/chive.html", "w") as f:
                f.write(html)
            log("Wrote HTML to /tmp/chive.html for debugging")
    assert html.strip().endswith("</html>"), (base, html)
    doc = pyquery.PyQuery(html)

    if debug:
        for title in doc("title").items():
            log("TITLE", title.text())
            break
        else:
            log("no title!")

    slots = list(doc("div.slot").items())
    if debug:
        log(f"Found {len(slots)} slots")
    if not slots:
        print(html)
        raise Exception("Busted DOM queries?")

    count = 0
    for slot in slots:
        for a in slot("a.full-card__image-link").items():
            href = a.attr("href")
            if not href.startswith(base):
                continue
            href = remove_utm_params(href)

            for m in a('meta[itemprop="url"]').items():
                # print("META", m.attr("content"))
                img = m.attr("content")
                if img:
                    # print("GOT META", img)
                    break
                else:
                    continue

            if href and img:
                log("Found card", href, img)
                break

            # # Old here
            # for img in a("img.card-thumb").items():
            #     img = img.attr("src")
            #     break
            # else:
            #     continue
            # break
        else:
            continue

        assert img.startswith("https"), img
        for a in slot('h1[itemprop="headline"] a').items():
            text = a.text().replace("\xa0", " ").strip()
            log("HEADLINE TEXT", repr(text))
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
        count += 1
        if limit and count >= limit:
            print("Card scrape limit reached!", count)
            break


def get_card(url):
    assert url.startswith("https://thechive.com"), url

    # The cache is really just to assure we don't run it more than once
    # in a short timeframe. ...by some accident or local dev.
    puppeteer_cache_key = "puppeteer_sucks:{}".format(
        hashlib.md5(url.encode("utf-8")).hexdigest()
    )
    html = cache.get(puppeteer_cache_key)
    if html is None:
        print("Sucking", url)
        html = puppeteer.suck(url)
        assert html, url
        assert html.strip().endswith("</html>"), (url, html)
        print("Sucked", url)
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
        print("NO 'h1#post-title'", url)
        if settings.DEBUG:
            raise Exception("Busted DOM queries?")
        return

    date = None
    for time_ in doc("header.article-header time[datetime]").items():
        date = time_.attr("datetime")
        break

    pictures = []
    # for figure in doc("div.gallery figure.gallery-item").items():
    for figure in doc("figure.gallery-item").items():
        caption = []
        caption_html = []
        gifsrc = None
        mp4src = None
        src = None
        for p in figure("figcaption.gallery-caption p").items():
            caption.append(p.text())
            caption_html.append(p.html())
        for img in figure("img.attachment-gallery-item-full").items():
            src = img.attr("src")
            gifsrc = img.attr("data-gifsrc")
            break
        else:
            for img in figure("img.attachment-gallery-item-hires").items():
                src = img.attr("src")
                break
        if not src:
            for video in figure("video.video-gif").items():
                for source in video("source").items():
                    if source.attr("type") == "video/mp4":
                        mp4src = source.attr("src")
                    break
                if mp4src:
                    src = video.attr("poster")
                break

        if not src:
            # Happens sometimes when it's just a bunch of Twitter quotes.
            # if settings.DEBUG:
            #     raise Exception("No src on {}".format(url))
            print(f"NO PICTURES (in {url}) figuree", figure)
            continue

        src = src.replace("http://", "https://")
        # assert src.startswith("https://"), src
        if gifsrc:
            gifsrc = gifsrc.replace("http://", "https://")
            # assert gifsrc.startswith("https://")

        combined_caption = "\n".join(
            [x.strip() for x in caption if x.replace("\xa0", " ").strip()]
        )
        combined_caption_html = "<br>".join(
            [
                x.strip()
                for x in caption_html
                if remove_html_comments(x).replace("\xa0", " ").strip()
            ]
        )

        pictures.append(
            {
                "img": src,
                "gifsrc": gifsrc,
                "mp4src": mp4src,
                "caption": combined_caption,
                "caption_html": combined_caption_html,
            }
        )

    return {"text": text, "pictures": pictures, "date": date}


def remove_html_comments(html_string):
    return re.sub("(<!--.*?-->)", "", html_string, flags=re.DOTALL)


def remove_utm_params(url):
    """Remove utm_postid and utm_editor from URL query string."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)

    # Remove the specified keys
    params.pop("utm_postid", None)
    params.pop("utm_editor", None)

    # Flatten the dict (parse_qs returns lists for values)
    filtered_params = {k: v[0] if len(v) == 1 else v for k, v in params.items()}

    # Reconstruct the URL
    new_query = urlencode(filtered_params, doseq=True)
    new_parsed = parsed._replace(query=new_query)

    return urlunparse(new_parsed)
