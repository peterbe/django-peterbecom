import re

from django.conf import settings
from huey import crontab
from huey.contrib.djhuey import periodic_task, task

from peterbecom.chiveproxy.models import Card
from peterbecom.chiveproxy.preload_image_proxies import load_all_image_proxies


def filter_pictures(pictures):
    filtered_pictures = []
    for picture in pictures:
        keep = True
        for banned_part in settings.BANNED_CHIVE_URL_PARTS:
            needles = [x for x in (picture.get("mp4src"), picture.get("img")) if x]
            if any(_is_banned(banned_part, needle) for needle in needles):
                print("SKIP THIS PICTURE!!!!")
                print(picture)
                keep = False
                break
        if keep:
            filtered_pictures.append(picture)
    return filtered_pictures


def _is_banned(banned_part: str | re.Pattern, needle: str) -> bool:
    if isinstance(banned_part, str):
        return banned_part in needle
    elif isinstance(banned_part, re.Pattern):
        return bool(banned_part.search(needle))
    return False


def remove_banned_pictures(limit=10, dry_run=False):

    for card in Card.objects.all().order_by("-created")[:limit]:
        updated_pictures = filter_pictures(card.data["pictures"])
        if updated_pictures != card.data["pictures"]:
            print(
                "REMOVED",
                [p for p in card.data["pictures"] if p not in updated_pictures],
            )
            if not dry_run:
                card.data["pictures"] = updated_pictures
                card.save()


@periodic_task(crontab(hour="*", minute="10"))
def remove_banned_pictures_periodically():
    remove_banned_pictures()


@task()
def preload_image_proxies_task(card_id: int, sleep_delay: float = 1):
    print("Preloading image proxies for", repr(card_id))
    card = Card.objects.get(id=card_id)
    load_all_image_proxies(card, sleep_delay=sleep_delay)
