from django import http
from django.conf import settings
from django.core.cache import cache
from django.views.decorators.cache import cache_control

from .sucks import get_card, get_cards


class ScrapingError(Exception):
    """Something went wrong."""


@cache_control(max_age=settings.DEBUG and 5 or 30 * 60, public=True)
def api_cards(request):
    cache_key = "cards"
    cards = cache.get(cache_key)
    if cards is None:
        cards = list(get_cards())
        cache.set(cache_key, cards, 30 * 60)
    context = {"cards": cards}
    return http.JsonResponse(context)


@cache_control(max_age=settings.DEBUG and 10 or 60 * 60, public=True)
def api_card(request, hash):
    cache_key = "card:{}".format(hash)
    card = cache.get(cache_key)
    if card is None:
        url = request.GET.get("url")
        if not url:
            return http.HttpResponseNotFound("No 'url'")
        card = get_card(url)
        if not card:
            raise ScrapingError(url)
        if card["pictures"]:
            cache.set(cache_key, card, 60 * 60)
        else:
            raise ScrapingError("no pictures! ({})".format(url))

    return http.JsonResponse(card)
