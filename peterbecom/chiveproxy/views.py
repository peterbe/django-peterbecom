from django.core.cache import cache
from django import http

from .sucks import get_cards, get_card


def api_cards(request):
    cache_key = "cards"
    cards = cache.get(cache_key)
    if cards is None:
        cards = list(get_cards())
        cache.set(cache_key, cards, 60 * 60)
    context = {"cards": cards}
    return http.JsonResponse(context)


def api_card(request, hash):
    cache_key = "card:{}".format(hash)
    card = cache.get(cache_key)
    if card is None:
        url = request.GET.get("url")
        if not url:
            return http.HttpResponseNotFound("No 'url'")
        card = get_card(url)
        cache.set(cache_key, card, 60 * 60)

    return http.JsonResponse(card)
