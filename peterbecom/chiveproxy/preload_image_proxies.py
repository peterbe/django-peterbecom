import time
from urllib.parse import urlencode, urlparse

import requests

from .models import Card, Picture


def _wrap_url(url: str) -> str:
    qs = urlencode({"url": url, "redirect_to_file": "true"})
    # qs = urlencode({"url": url})
    return f"https://chive.peterbe.com/api/imageproxy?{qs}"


def _fetch_image(url: str):

    try:
        response = requests.get(url)
        response.raise_for_status()
        return response
    except requests.RequestException as e:
        print(f"Failed to fetch image from {url}: {e}")
        return None


def get_all_image_proxies(card: Card):
    for picture in Picture.objects.filter(card=card):
        if mp4 := picture.mp4src:
            wrapped_url = _wrap_url(mp4)
            yield (picture.id, "mp4", wrapped_url)
            # wrapped_urls.append(wrapped_url)
        if img := picture.img:
            wrapped_url = _wrap_url(img)
            yield (picture.id, "img", wrapped_url)
            # wrapped_urls.append(wrapped_url)



def load_all_image_proxies(card: Card, sleep_delay: float = 0.1):
    print(f"Loading all image proxies for {card}")
    for picture_id, key, wrapped_url in get_all_image_proxies(card):
        response = _fetch_image(wrapped_url)
        print("RESPONSE", response)
        print(f"Fetched image response for picture_id {picture_id}, key {key}: {response}")
        _save_redirected_url(picture_id, key, response.url)
        print("URL:                 ", response.url)
        print("Content-Length:      ", response.headers["content-length"])
        print("Content-Type:        ", response.headers["content-type"])
        print("X-Destination-Cache: ", response.headers.get("x-destination-cache"))
        if sleep_delay:
            time.sleep(sleep_delay)


def _save_redirected_url(picture_id: int, key: str, url: str):
    path = urlparse(url).path
    # print(f"{path=}")
    rel_path = path.replace('/image_proxy/', '')
    picture = Picture.objects.get(id=picture_id)
    print("BEFORE", picture.image_proxy_conversions)
    if key not in picture.image_proxy_conversions:
        picture.image_proxy_conversions[key] = rel_path
        picture.save()
    print("AFTER", picture.image_proxy_conversions)
    # if key == "mp4":
    #     picture.mp4src = path
    # elif key == "img":
    #     picture.img = path
    # picture.save()
