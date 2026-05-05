import time
from subprocess import TimeoutExpired

from django import http
from django.conf import settings
from django.core.cache import cache
from django.db.models import Min
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.timesince import timesince
from django.views.decorators.cache import cache_control
from huey import crontab
from huey.contrib.djhuey import periodic_task

from .models import Card
from .sucks import get_card, get_cards


class JsonResponse(http.JsonResponse):
    def __init__(self, data, *args, **kwargs):
        self.data = data
        super().__init__(data, *args, **kwargs)


class ScrapingError(Exception):
    """Something went wrong."""


@cache_control(max_age=settings.DEBUG and 10 or 60 * 60, public=True)
def api_cards(request):
    context = {"cards": []}
    qs = Card.objects
    batch_size = 80

    since = request.GET.get("since")
    if since == "null":
        since = None
    if since:
        qs = qs.filter(created__lt=since)

    search = request.GET.get("search")
    if search:
        qs = qs.filter(text__search=search)
        context["search"] = {"string": search, "count": qs.count()}

    now = timezone.now()
    for card in qs.order_by("-created")[:batch_size]:
        human_time = timesince(card.created).replace("\xa0", " ")
        age = (now - card.created).total_seconds()
        if age < 60:
            human_time = f"{int(age)} seconds ago"
        else:
            human_time += " ago"
        if "img" not in card.data:
            continue

        if not card.data["pictures"]:
            print(f"WARNING! {card!r} does not have any pictures")
            continue

        context["cards"].append(
            dict(
                # card.data,
                text=card.data["text"],
                img=card.data["img"],
                url=card.url,
                id=card.id,
                created=card.created,
                human_time=human_time,
                # This last one is for legacy backwards compat
                uri=card.id,
            )
        )

    context["_oldest_card"] = Card.objects.all().aggregate(oldest=Min("created"))[
        "oldest"
    ]
    return JsonResponse(context)


def _cards_log(*args):
    print("CARDS", *args, f"({timezone.now()})")


@periodic_task(crontab(hour="*", minute="1"))
def update_cards_periodically():
    _cards_log("Updating cards periodically")
    count_updated, count_tried = update_cards(limit=15)
    _cards_log(f"Updated {count_updated} cards (tried {count_tried})")


@periodic_task(crontab(hour="*", minute="10"))
def update_cards_without_pictures_periodically():
    _cards_log("Updating cards without pictures")
    qs = Card.objects
    for card in qs.order_by("-created")[:100]:
        if card.data["pictures"]:
            continue
        retry_cache_key = "retried:{}".format(card.pk)
        _cards_log("CARDS:", retry_cache_key, repr(card), "HAS NO PICTURES")

        if not cache.get(retry_cache_key):
            _cards_log(f"Retrying card {card!r}...")
            try:
                _cards_log(f"CARDS: Getting card (without pictures) {card.url}")
                t0 = time.time()
                card.data = get_card(card.url)
                card.save()
                took_seconds = time.time() - t0
                _cards_log(
                    f"CARDS: Fixed {card!r}: {len(card.data['pictures'])} pictures "
                    f"(took {took_seconds:.1f} seconds)"
                )
            except Exception as e:
                _cards_log(f"CARDS: Error on get_card({card.url!r}):", e)
            finally:
                cache.set(
                    retry_cache_key,
                    str(timezone.now()),
                    settings.DEBUG and 60 or 60 * 60,
                )


def update_cards(limit=None, debug=False):
    count_updated = count_tried = 0
    for card in sorted(get_cards(limit=limit, debug=debug), key=lambda c: c["date"]):
        url = card.pop("url")
        if not Card.objects.filter(url=url).exists():
            count_tried += 1
            key = f"get_card_failures:{url}"
            previous_value = cache.get(key) or 0
            _cards_log(f"PREVIOUS FAILURES {url}: {previous_value}")
            try:
                _cards_log(f"CARDS: Getting card {url}")
                t0 = time.time()
                data = get_card(url)
                if data:
                    card.update(data)
                    Card.objects.create(url=url, data=card)
                    count_updated += 1
                took_seconds = time.time() - t0
                _cards_log(
                    f"CARDS: Got card {url} ({'got data' if data else 'no data!'})"
                    f" (took {took_seconds:.1f} seconds)"
                )
            except TimeoutExpired:
                new_value = previous_value + 1
                cache.set(key, new_value, 60 * 60)
    return count_updated, count_tried


@cache_control(max_age=settings.DEBUG and 10 or 60 * 60 * 6, public=True)
def api_card(request, pk):
    card = get_object_or_404(Card, pk=pk)
    if request.GET.get("url"):
        if request.GET["url"] != card.url:
            return http.HttpResponseBadRequest("wrong URL")
    if not card.data["pictures"]:
        return http.Http404("Card has no pictures")
    return JsonResponse(
        {
            "id": card.id,
            "text": card.data["text"],
            "date": card.created,
            "pictures": card.data["pictures"],
        }
    )
