import hashlib
import time
from subprocess import TimeoutExpired
from urllib.parse import urlparse

import requests
from django import forms, http
from django.conf import settings
from django.core.cache import cache
from django.db.models import Min
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.timesince import timesince
from django.views.decorators.cache import cache_control
from huey import crontab
from huey.contrib.djhuey import periodic_task
from PIL import Image

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
            {
                "text": card.data["text"],
                "img": card.data["img"],
                "url": card.url,
                "id": card.id,
                "created": card.created,
                "human_time": human_time,
                # This last one is for legacy backwards compat
                "uri": card.id,
            }
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
    try:
        count_updated, count_tried = update_cards(limit=15)
        _cards_log(f"Updated {count_updated} cards (tried {count_tried})")
    except Exception as e:
        _cards_log("Error in update_cards_periodically:", e)
        raise


@periodic_task(crontab(hour="*", minute="10"))
def update_cards_without_pictures_periodically():
    _cards_log("Updating cards without pictures")
    qs = Card.objects
    for card in qs.order_by("-created")[:100]:
        if card.data["pictures"]:
            continue
        retry_cache_key = f"retried:{card.pk}"
        _cards_log("retry cache key:", retry_cache_key, repr(card), "HAS NO PICTURES")

        if not cache.get(retry_cache_key):
            _cards_log(f"Retrying card {card!r}...")
            try:
                _cards_log(f"Getting card (without pictures) {card.url}")
                t0 = time.time()
                card.data = get_card(card.url)
                card.save()
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
                _cards_log(f"Getting card {url}")
                t0 = time.time()
                data = get_card(url)
                if data:
                    card.update(data)
                    Card.objects.create(url=url, data=card)
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


@cache_control(max_age=settings.DEBUG and 10 or 60 * 60 * 6, public=True)
def api_card(request, pk):
    card = get_object_or_404(Card, pk=pk)
    if request.GET.get("url") and request.GET["url"] != card.url:
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


class ImageProxyForm(forms.Form):
    url = forms.URLField(required=True)

    def clean_url(self):
        url = self.cleaned_data.get("url")
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise forms.ValidationError("Invalid URL")
        if parsed.scheme != "https":
            raise forms.ValidationError("Invalid URL (not https)")

        if settings.CHIVEPROXY_NETLOC not in parsed.netloc:
            raise forms.ValidationError("Invalid netloc")

        if not parsed.path.startswith(settings.CHIVEPROXY_PATH_PREFIX):
            raise forms.ValidationError("Invalid path prefix")

        path_lowered = parsed.path.lower()
        if not (path_lowered.endswith((".jpg", ".png"))):
            raise forms.ValidationError(f"Invalid file extension ({path_lowered})")

        return url


@cache_control(max_age=settings.DEBUG and 10 or 60 * 60 * 6, public=True)
def image_proxy(request):
    form = ImageProxyForm(request.GET)
    if not form.is_valid():
        return http.HttpResponseBadRequest(form.errors.as_text())
    url = form.cleaned_data["url"]

    cache_root = settings.BASE_DIR / "cache" / "image_proxy"
    if not cache_root.exists():
        cache_root.mkdir(parents=True)

    seed = f"{settings.SECRET_KEY}:{url}"
    seeded = seeded_token(seed)
    file_extension = urlparse(url).path.split(".")[-1]
    prefix = ""
    if settings.RUNNING_TESTS:
        prefix = "test-"
    origin_destination_file_name = cache_root / f"{prefix}{seeded}.{file_extension}"
    destination_file_name = (
        cache_root / seeded[:2] / seeded[2:4] / f"{prefix}{seeded[4:]}.webp"
    )
    if not destination_file_name.parent.exists():
        destination_file_name.parent.mkdir(parents=True)
    if not destination_file_name.exists():

        def file_size(b: int) -> str:
            for unit in ["bytes", "KB", "MB", "GB"]:
                if b < 1024.0:
                    return f"{b:.2f} {unit}"
                b /= 1024.0
            return f"{b:.2f} TB"

        if not origin_destination_file_name.exists():
            with open(origin_destination_file_name, "wb") as f:
                f.write(fetch_image(url))
            print(
                f"IMAGE_PROXY: Fetched image from URL: {url} -> {origin_destination_file_name} "
                f"({file_size(origin_destination_file_name.stat().st_size)})"
            )

        image = Image.open(origin_destination_file_name)
        image.save(destination_file_name, "webp", quality=99)
        print(
            f"IMAGE_PROXY: Converted fetched image from URL: "
            f"{origin_destination_file_name} -> {destination_file_name} "
            f"({file_size(destination_file_name.stat().st_size)})"
        )

        origin_destination_file_name.unlink()

    response = http.HttpResponse()
    response["Content-Type"] = "image/webp"
    with open(destination_file_name, "rb") as f:
        image_data = f.read()
    response.write(image_data)
    return response


def fetch_image(url: str) -> bytes:
    response = requests.get(url)
    response.raise_for_status()
    return response.content


def seeded_token(seed: str, length=12) -> str:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return digest[:length]
