from django.conf import settings
from huey import crontab
from huey.contrib.djhuey import periodic_task

from .models import Card


def filter_pictures(pictures):
    filtered_pictures = []
    for picture in pictures:
        keep = True
        for banned_part in settings.BANNED_CHIVE_URL_PARTS:
            needles = [x for x in (picture.get("mp4src"), picture.get("img")) if x]
            if any(banned_part in needle for needle in needles):
                print("SKIP THIS PICTURE!!!!")
                print(picture)
                keep = False
                break
        if keep:
            filtered_pictures.append(picture)
    return filtered_pictures


def remove_banned_pictures(limit=10):
    for card in Card.objects.all().order_by("-created")[:limit]:
        updated_pictures = filter_pictures(card.data["pictures"])
        if updated_pictures != card.data["pictures"]:
            print(
                "REMOVED",
                [p for p in card.data["pictures"] if p not in updated_pictures],
            )
            card.data["pictures"] = updated_pictures
            card.save()


@periodic_task(crontab(hour="*", minute="10"))
def remove_banned_pictures_periodically():
    remove_banned_pictures()
