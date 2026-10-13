import re
import time

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


@periodic_task(crontab(minute="30"))
def delete_old_image_proxy_files():
    _delete_old_image_proxy_files()


def _delete_old_image_proxy_files():
    cache_root = settings.IMAGE_PROXY_CACHE_ROOT
    if not cache_root.exists():
        print(f"WARNING {cache_root} does not exist")
        return

    count = 0
    MAX_COUNT = 10
    MIN_AGE_DAYS = 100

    for file_path in cache_root.rglob("*"):
        if file_path.is_file():
            age_seconds = time.time() - file_path.stat().st_mtime
            age_hours = age_seconds / 3600
            age_days = age_hours / 24
            if age_days > MIN_AGE_DAYS:
                print(
                    f"Deleting old image proxy file: {file_path}, "
                    f"Age: {age_days:.1f} days"
                )
                file_path.unlink()
                count += 1

                count_files_in_dir = len(list(file_path.parent.glob("*")))
                if not count_files_in_dir:
                    print("No more files in this directory")
                    file_path.parent.rmdir()

        if count >= MAX_COUNT:
            break


@task()
def preload_image_proxies_task(card_id: int, sleep_delay: float = 1):
    print("Preloading image proxies for", repr(card_id))
    card = Card.objects.get(id=card_id)
    load_all_image_proxies(card, sleep_delay=sleep_delay)
