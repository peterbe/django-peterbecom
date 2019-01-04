from django import http
from django.conf import settings
from django.core.cache import cache
from django.db.models import Min
from django.utils import timezone
from django.utils.timesince import timesince
from django.views.decorators.cache import cache_control
from django.shortcuts import get_object_or_404
from huey.contrib.djhuey import task

from .models import Card
from .sucks import get_card, get_cards


class ScrapingError(Exception):
    """Something went wrong."""


@cache_control(max_age=settings.DEBUG and 10 or 60, public=True)
def api_cards(request):
    context = {"cards": []}
    qs = Card.objects
    batch_size = 10

    since = request.GET.get("since")
    if since == "null":
        since = None
    if since:
        qs = qs.filter(created__lt=since)

    now = timezone.now()
    for card in qs.order_by("-created")[:batch_size]:
        human_time = timesince(card.created).replace("\xa0", " ")
        age = (now - card.created).total_seconds()
        if age < 60:
            human_time = "{} seconds ago".format(int(age))
        human_time += " ago"
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

    context["_updating"] = False
    if not since and not cache.get("updated-cards-recently"):
        cache.set("updated-cards-recently", True, settings.DEBUG and 60 or 30 * 60)
        print("CALLING UPDATE_CARDS!")
        update_cards_task()
        context["_updating"] = True

    return http.JsonResponse(context)


@task()
def update_cards_task():
    update_cards()


def update_cards():
    for card in sorted(get_cards(), key=lambda c: c["date"]):
        print("CARD", repr(card["date"]))
        url = card.pop("url")
        if not Card.objects.filter(url=url).exists():
            card.update(get_card(url))
            print("\tCREATED CARD", url)
            Card.objects.create(url=url, data=card)


@cache_control(max_age=settings.DEBUG and 10 or 60 * 60, public=True)
def api_card(request, pk):
    card = get_object_or_404(Card, pk=pk)
    return http.JsonResponse(
        {
            "id": card.id,
            "text": card.data["text"],
            "date": card.created,
            "pictures": card.data["pictures"],
        }
    )
