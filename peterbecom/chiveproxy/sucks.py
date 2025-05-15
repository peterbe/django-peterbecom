import hashlib
import re

from cachetools import TTLCache, cached
from django.conf import settings
from scrapling.fetchers import Fetcher

# from . import puppeteer

long_ttl_cache = TTLCache(maxsize=50, ttl=60 * 60)
short_ttl_cache = TTLCache(maxsize=10, ttl=60)


def make_it_more_iso(datestr):
    return re.sub(r"\b(\d)\b", r"0\1", datestr)


# def get_cards(limit=None, debug=False):
#     base = "https://thechive.com/"
#     html = puppeteer.suck(base)
#     assert html, base
#     assert html.strip().endswith("</html>"), (base, html)
#     doc = pyquery.PyQuery(html)

#     if debug:
#         for title in doc("title").items():
#             print("TITLE", title.text())
#             break
#         else:
#             print("no title!")
#         # for element in doc("h1.card-title").items():
#         #     print("h1", element.text())

#     count = 0
#     for slot in doc("div.slot").items():
#         for a in slot("a.card-img-link").items():
#             href = a.attr("href")
#             if not href.startswith(base):
#                 continue
#             for img in a("img.card-thumb").items():
#                 img = img.attr("src")
#                 break
#             else:
#                 continue
#             break
#         else:
#             continue

#         assert img.startswith("https"), img
#         for a in slot("h1.post-title a").items():
#             text = a.text().replace("\xa0", " ").strip()
#             if text.lower().endswith("(video)"):
#                 continue
#             if text.lower().endswith("(vote)"):
#                 continue
#             break
#         else:
#             continue

#         date = None
#         human_time = None
#         for time_ in slot("time[datetime]").items():
#             date = time_.attr("datetime")
#             date = make_it_more_iso(date)
#             human_time = time_.text()  # Not needed?
#             break

#         uri = hashlib.md5(href.encode("utf-8")).hexdigest()[:8]
#         yield {
#             "url": href,
#             "uri": uri,
#             "text": text,
#             "img": img,
#             "date": date,
#             "human_time": human_time,
#         }
#         count += 1
#         if limit and count >= limit:
#             print("Card scrape limit reached!", count)
#             break


@cached(cache=short_ttl_cache)
def get_cards(limit=None, debug=False):
    base = "https://thechive.com/"
    page = Fetcher.get(base, stealthy_headers=True)
    assert page.status == 200, page.status

    # print(page)
    count = 0
    for slot in page.css("div.slot"):
        # print("SLOT:", slot)
        for a in slot.css("a.card-img-link"):
            href = a.attrib["href"]
            # print("A:", href)
            if not href.startswith(base):
                continue
            for img_element in a.css("img.card-thumb"):
                img = img_element.attrib["src"]
                break
            else:
                continue
            break
        else:
            continue

        assert img.startswith("https"), img
        for a in slot.css("h1.post-title a"):
            text = a.text.replace("\xa0", " ").strip()

            if text.lower().endswith("(video)"):
                continue
            if text.lower().endswith("(vote)"):
                continue
            break
        else:
            continue

        date = None
        human_time = None
        for time_ in slot.css("time[datetime]"):
            date = time_.attrib["datetime"]
            date = make_it_more_iso(date)
            human_time = time_.get_all_text().split("\n")[0].strip()
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
    yield None


# def get_card(url):
#     assert url.startswith("https://thechive.com"), url

#     # The cache is really just to assure we don't run it more than once
#     # in a short timeframe. ...by some accident or local dev.
#     puppeteer_cache_key = "puppeteer_sucks:{}".format(
#         hashlib.md5(url.encode("utf-8")).hexdigest()
#     )
#     html = cache.get(puppeteer_cache_key)
#     if html is None:
#         print("Sucking", url)
#         html = puppeteer.suck(url)
#         assert html, url
#         assert html.strip().endswith("</html>"), (url, html)
#         print("Sucked", url)
#         if html:
#             cache.set(puppeteer_cache_key, html, 60)
#     else:
#         print("No need sucking", url, "(cached)")

#     doc = pyquery.PyQuery(html)

#     for h1 in doc("h1#post-title").items():
#         text = h1.text()
#         text = text.replace("\xa0", " ").strip()
#         break
#     else:
#         print("NO 'h1#post-title'", url)
#         if settings.DEBUG:
#             raise Exception("Busted DOM queries?")
#         return

#     date = None
#     for time_ in doc("header.article-header time[datetime]").items():
#         date = time_.attr("datetime")
#         break

#     pictures = []
#     # for figure in doc("div.gallery figure.gallery-item").items():
#     for figure in doc("figure.gallery-item").items():
#         caption = []
#         caption_html = []
#         gifsrc = None
#         mp4src = None
#         src = None
#         for p in figure("figcaption.gallery-caption p").items():
#             caption.append(p.text())
#             caption_html.append(p.html())
#         for img in figure("img.attachment-gallery-item-full").items():
#             src = img.attr("src")
#             gifsrc = img.attr("data-gifsrc")
#             break
#         else:
#             for img in figure("img.attachment-gallery-item-hires").items():
#                 src = img.attr("src")
#                 break
#         if not src:
#             for video in figure("video.video-gif").items():
#                 for source in video("source").items():
#                     if source.attr("type") == "video/mp4":
#                         mp4src = source.attr("src")
#                     break
#                 if mp4src:
#                     src = video.attr("poster")
#                 break

#         if not src:
#             # Happens sometimes when it's just a bunch of Twitter quotes.
#             # if settings.DEBUG:
#             #     raise Exception("No src on {}".format(url))
#             print(f"NO PICTURES (in {url}) figuree", figure)
#             continue

#         src = src.replace("http://", "https://")
#         # assert src.startswith("https://"), src
#         if gifsrc:
#             gifsrc = gifsrc.replace("http://", "https://")
#             # assert gifsrc.startswith("https://")

#         combined_caption = "\n".join(
#             [x.strip() for x in caption if x.replace("\xa0", " ").strip()]
#         )
#         combined_caption_html = "<br>".join(
#             [
#                 x.strip()
#                 for x in caption_html
#                 if remove_html_comments(x).replace("\xa0", " ").strip()
#             ]
#         )

#         pictures.append(
#             {
#                 "img": src,
#                 "gifsrc": gifsrc,
#                 "mp4src": mp4src,
#                 "caption": combined_caption,
#                 "caption_html": combined_caption_html,
#             }
#         )

#     return {"text": text, "pictures": pictures, "date": date}


@cached(cache=long_ttl_cache)
def get_card(url):
    assert url.startswith("https://thechive.com"), url

    # # The cache is really just to assure we don't run it more than once
    # # in a short timeframe. ...by some accident or local dev.
    # puppeteer_cache_key = "puppeteer_sucks:{}".format(
    #     hashlib.md5(url.encode("utf-8")).hexdigest()
    # )
    # html = cache.get(puppeteer_cache_key)
    # if html
    page = Fetcher.get(url, stealthy_headers=True)
    assert page.status == 200, page.status

    for h1 in page.css("h1#post-title"):
        text = h1.text.replace("\xa0", " ").strip()
        break
    else:
        print("NO 'h1#post-title'", url)
        if settings.DEBUG:
            raise Exception("Busted DOM queries?")
        return

    date = None
    for time_ in page.css("header.article-header time[datetime]"):
        date = time_.attrib["datetime"]
        break

    pictures = []
    for figure in page.css("figure.gallery-item"):
        caption = []
        caption_html = []
        gifsrc = None
        mp4src = None
        src = None
        for p in figure.css("figcaption.gallery-caption p"):
            caption.append(p.text)
            caption_html.append(p.get_all_text())
        for img in figure.css("img.attachment-gallery-item-full"):
            src = img.attrib["src"]
            # print(dir(img))
            # print([x for x in dir(img) if "attr" in x])
            gifsrc = img.attrib.get("data-gifsrc")
            break
        else:
            for img in figure.css("img.attachment-gallery-item-hires"):
                src = img.attrib["src"]
                break
        if not src:
            for video in figure.css("video.video-gif"):
                for source in video.css("source"):
                    if source.attrib["type"] == "video/mp4":
                        mp4src = source.attrib["src"]
                    break
                if mp4src:
                    src = video.attrib["poster"]
                break
        if not src:
            # Happens sometimes when it's just a bunch of Twitter quotes.
            print(f"NO PICTURES (in {url}) figure", figure.html_string)
            continue

        src = src.replace("http://", "https://")
        if gifsrc:
            gifsrc = gifsrc.replace("http://", "https://")

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
