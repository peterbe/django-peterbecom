import time
from subprocess import TimeoutExpired

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from peterbecom.chiveproxy.tasks import preload_image_proxies_task

from .models import Card, Picture
from .sucks import get_card, get_cards


def _cards_log(*args):
    print("CARDS", *args, f"({timezone.now()})")


def update_cards_without_pictures():
    qs = Card.objects
    for card in qs.order_by("-created")[:100]:
        if Picture.objects.filter(card=card).exists():
            continue
        retry_cache_key = f"retried:{card.pk}"
        _cards_log("retry cache key:", retry_cache_key, repr(card), "HAS NO PICTURES")

        if not cache.get(retry_cache_key):
            _cards_log(f"Retrying card {card!r}...")
            try:
                _cards_log(f"Getting card (without pictures) {card.url}")
                t0 = time.time()
                card.data = get_card(card.url)
                pictures = card.data.pop("pictures")
                with transaction.atomic():
                    for order_index, picture in enumerate(pictures):
                        Picture.objects.create(
                            card=card,
                            img=picture["img"],
                            gifsrc=picture["gifsrc"] or None,
                            mp4src=picture["mp4src"] or None,
                            caption=picture["caption"],
                            caption_html=picture["caption_html"],
                            order_index=order_index,
                        )
                    card.data = card.data
                    card.save()
                preload_image_proxies_task(card.id)
                took_seconds = time.time() - t0
                _cards_log(
                    f"Fixed {card!r}: {len(card.data['pictures'])} pictures "
                    f"(took {took_seconds:.1f} seconds)"
                )
            except Exception as e:  # noqa: BLE001
                _cards_log(f"Error on get_card({card.url!r}):", e)
            finally:
                cache.set(
                    retry_cache_key,
                    str(timezone.now()),
                    settings.DEBUG and 60 or 60 * 60,
                )


def update_cards(limit=None, debug=False, dry_run=False):
    count_updated = count_tried = 0
    for card in sorted(get_cards(limit=limit, debug=debug), key=lambda c: c["date"]):
        url = card.pop("url")
        if not Card.objects.filter(url=url).exists():
            count_tried += 1
            key = f"get_card_failures:{url}"
            previous_value = cache.get(key) or 0
            _cards_log(f"PREVIOUS FAILURES {url}: {previous_value}")
            try:
                _cards_log(f"Getting card {url}")
                t0 = time.time()
                data = get_card(url)
                if data and data.get("pictures"):
                    pictures = data.pop("pictures")
                    card.update(data)
                    if not dry_run:
                        with transaction.atomic():
                            card_obj = Card.objects.create(url=url, data=card)

                            pictures_objs = []
                            for order_index, picture in enumerate(pictures):
                                pictures_objs.append(
                                    Picture(
                                        card=card_obj,
                                        img=picture["img"],
                                        gifsrc=picture["gifsrc"] or None,
                                        mp4src=picture["mp4src"] or None,
                                        caption=picture["caption"],
                                        caption_html=picture["caption_html"],
                                        order_index=order_index,
                                    )
                                )
                            Picture.objects.bulk_create(pictures_objs)
                        preload_image_proxies_task(card_obj.id)
                    count_updated += 1
                took_seconds = time.time() - t0
                _cards_log(
                    f"Got card {url} ({'got data' if data else 'no data!'})"
                    f" (took {took_seconds:.1f} seconds)"
                )

            except TimeoutExpired:
                new_value = previous_value + 1
                cache.set(key, new_value, 60 * 60)
    return count_updated, count_tried
