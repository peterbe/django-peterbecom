import hashlib

import pyquery


def get_cards():
    base = "http://thechive.com/"
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
        for a in slot("h3.post-title a").items():
            text = a.text().replace("\xa0", " ").strip()
            if text.endswith("(Video)"):
                continue
            if text.endswith("(Vote)"):
                continue
            break
        else:
            continue

        date = None
        human_time = None
        for time_ in slot("time[datetime]").items():
            date = time_.attr("datetime")
            human_time = time_.text()
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
    assert url.startswith("http://thechive.com"), url
    doc = pyquery.PyQuery(url)

    for h1 in doc("h1#post-title").items():
        text = h1.text()
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
        for p in figure("figcaption.gallery-caption").items():
            caption.append(p.text())
        for img in figure("img.attachment-gallery-item-full").items():
            src = img.attr("src")
            gifsrc = img.attr("data-gifsrc")
            break
        else:
            for img in figure("img.attachment-gallery-item-hires").items():
                src = img.attr("src")
                break

        pictures.append({"img": src, "gifsrc": gifsrc, "caption": "\n".join(caption)})

    return {"text": text, "pictures": pictures, "date": date}
