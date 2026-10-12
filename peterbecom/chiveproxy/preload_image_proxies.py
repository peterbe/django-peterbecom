import time

import requests

from .models import Card


def _wrap_url(url: str) -> str:
    from urllib.parse import urlencode

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


def load_all_image_proxies(card: Card, sleep_delay: float = 0.1):
    print(f"Loading all image proxies for {card}")
    for picture in card.data.get("pictures", []):
        wrapped_urls = []
        if mp4 := picture.get("mp4src"):
            wrapped_url = _wrap_url(mp4)
            wrapped_urls.append(wrapped_url)
        if img := picture.get("img"):
            wrapped_url = _wrap_url(img)
            wrapped_urls.append(wrapped_url)

        for wrapped_url in wrapped_urls:
            print(f"Loading image proxy URL: {wrapped_url}")
            response = _fetch_image(wrapped_url)
            print(f"Fetched image response: {response}")
            print("URL:           ", response.url)
            print("Content-Length:", response.headers["content-length"])
            print("Content-Type:  ", response.headers["content-type"])
            if sleep_delay:
                time.sleep(sleep_delay)
