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
        if "img" not in card.data:
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
    return http.JsonResponse(context)


@periodic_task(crontab(hour="*"))
def update_cards_periodically():
    update_cards(limit=5)


def update_cards(limit=None):
    for card in sorted(get_cards(limit=limit), key=lambda c: c["date"]):
        url = card.pop("url")
        if not Card.objects.filter(url=url).exists():
            data = get_card(url)
            if data:
                card.update(data)
                Card.objects.create(url=url, data=card)


@cache_control(max_age=settings.DEBUG and 10 or 60 * 60, public=True)
def api_card(request, pk):
    card = get_object_or_404(Card, pk=pk)
    if request.GET.get("url"):
        if request.GET["url"] != card.url:
            return http.HttpResponseBadRequest("wrong URL")
    if not card.data["pictures"]:
        # Try again! ...if you haven't already
        retry_cache_key = "retried:{}".format(pk)
        if not cache.get(retry_cache_key):
            card.data = get_card(card.url)
            card.save()
            cache.set(retry_cache_key, str(timezone.now()), settings.DEBUG and 6 or 60)
    return http.JsonResponse(
        {
            "id": card.id,
            "text": card.data["text"],
            "date": card.created,
            "pictures": card.data["pictures"],
        }
    )
