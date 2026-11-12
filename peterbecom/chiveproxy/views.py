import shutil
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from django import forms, http
from django.conf import settings
from django.db import transaction
from django.db.models import Min, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.cache import patch_cache_control
from django.views.decorators.cache import cache_control
from huey import crontab
from huey.contrib.djhuey import periodic_task
from PIL import Image, UnidentifiedImageError

from peterbecom.chiveproxy.update_cards import (
    update_cards,
    update_cards_without_pictures,
)

from .image_proxy_utils import (
    NO_CONVERT_FILE_EXTENSIONS,
    url_to_destination,
)
from .models import Card, Picture


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

    for card in qs.order_by("-created")[:batch_size]:
        if "img" not in card.data:
            continue

        count_pictures = Picture.objects.filter(card=card).count()

        # # TEMPORARY CODE
        # if not count_pictures and card.data.get("pictures"):
        #     _migrate_legacy_card(card)
        #     count_pictures = Picture.objects.filter(card=card).count()

        if not count_pictures:
            print(f"WARNING! {card!r} does not have any pictures")
            continue

        context["cards"].append(
            {
                "text": card.data["text"],
                "img": card.data["img"],
                "url": card.url,
                "id": card.id,
                "created": card.created,
                "human_time": "",
                "count_pictures": count_pictures,
                # This last one is for legacy backwards compat
                "uri": card.id,
            }
        )

    context["_oldest_card"] = Card.objects.all().aggregate(oldest=Min("created"))[
        "oldest"
    ]
    return JsonResponse(context)


class SearchPicturesForm(forms.Form):
    query = forms.CharField(required=True)
    batch_size = forms.IntegerField(required=False)

    def clean_query(self):
        query = self.cleaned_data.get("query")
        if not query:
            raise forms.ValidationError("Query is required")
        query = query.strip()
        if len(query) < 2:
            raise forms.ValidationError("Query must be at least 2 characters long")
        return query

    def clean_batch_size(self):
        batch_size = self.cleaned_data.get("batch_size")
        if batch_size is None:
            return 10
        if batch_size <= 0:
            raise forms.ValidationError("Batch size must be a positive integer")
        if batch_size > 100:
            raise forms.ValidationError("Batch size must not exceed 100")
        return batch_size


@cache_control(max_age=settings.DEBUG and 10 or 60 * 60, public=True)
def api_search_pictures(request):
    context = {
        "pictures": [],
        "metadata": {},
    }
    form = SearchPicturesForm(request.GET)
    if not form.is_valid():
        return http.HttpResponseBadRequest(form.errors.as_text())

    query = form.cleaned_data["query"]
    context["metadata"]["query"] = query

    pictures = Picture.objects.order_by("-card__created", "order_index").filter(
        Q(caption__search=query) | Q(transcript__isnull=False, transcript__search=query)
    )
    t0 = time.time()
    context["metadata"]["count"] = pictures.count()
    pictures = pictures[: form.cleaned_data["batch_size"]]

    fields = (
        "id",
        "card_id",
        "img",
        "gifsrc",
        "mp4src",
        "caption",
        "caption_html",
        "transcript",
        "card__id",
        "card__text",
        "card__created",
    )

    context["metadata"]["batch_size"] = form.cleaned_data["batch_size"]

    for picture in pictures.values(*fields):
        context["pictures"].append(
            {
                "id": picture["id"],
                # "card_id": picture["card_id"],
                "img": picture["img"],
                "gifsrc": picture["gifsrc"] or None,
                "mp4src": picture["mp4src"] or None,
                "caption": picture["caption"],
                "caption_html": picture["caption_html"],
                "transcript": picture["transcript"],
                "card": {
                    "id": picture["card__id"],
                    "text": picture["card__text"],
                    "date": picture["card__created"],
                },
            }
        )

    t1 = time.time()
    context["metadata"]["took_seconds"] = t1 - t0
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
    update_cards_without_pictures()


def _migrate_legacy_card(card: Card):
    with transaction.atomic():
        pictures = card.data.pop("pictures")
        pictures_objs = []
        for order_index, picture in enumerate(pictures):
            pictures_objs.append(
                Picture(
                    card=card,
                    img=picture["img"],
                    gifsrc=picture.get("gifsrc") or None,
                    mp4src=picture["mp4src"] or None,
                    caption=picture["caption"],
                    caption_html=picture["caption_html"],
                    order_index=order_index,
                )
            )
        Picture.objects.bulk_create(pictures_objs)
        card.data = card.data
        card.save()


@cache_control(max_age=settings.DEBUG and 10 or 60 * 60 * 6, public=True)
def api_card(request, pk):
    card = get_object_or_404(Card, pk=pk)
    if request.GET.get("url") and request.GET["url"] != card.url:
        return http.HttpResponseBadRequest("wrong URL")

    # TEMPORARY CODE
    if card.data.get("pictures"):
        print("LEGACY!")
        _migrate_legacy_card(card)

    pictures = []
    qs = Picture.objects.filter(card=card).order_by("order_index")
    for picture in qs.values():
        pictures.append(
            {
                "id": picture["id"],
                "img": picture["img"],
                "gifsrc": picture["gifsrc"] or None,
                "mp4src": picture["mp4src"] or None,
                "caption": picture["caption"],
                "caption_html": picture["caption_html"],
                "transcript": picture["transcript"],
            }
        )
    if not pictures:
        return http.Http404("Card has no pictures")
    return JsonResponse(
        {
            "id": card.id,
            "text": card.data["text"],
            "date": card.created,
            "pictures": pictures,
        }
    )


class ImageProxyForm(forms.Form):
    url = forms.URLField(required=True)
    redirect_to_file = forms.BooleanField(required=False)

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
        if not (
            path_lowered.endswith((".jpg", ".png", ".webp", ".jpeg", ".mp4", ".avif"))
        ):
            raise forms.ValidationError(f"Invalid file extension ({path_lowered})")

        return url


def image_proxy(request):
    form = ImageProxyForm(request.GET)
    if not form.is_valid():
        print(
            f"IMAGE_PROXY: Invalid form: {form.errors.as_json()}  "
            f"Query string: {list(request.GET.items())}"
        )
        return http.HttpResponseBadRequest(form.errors.as_text())
    url = form.cleaned_data["url"]

    destination_cache: list[str] = []
    destination = url_to_destination(url)
    destination_file_extension = destination["destination_file_extension"]
    origin_destination_file_name = destination["origin_destination_file_name"]
    destination_file_name = destination["destination_file_name"]

    if not destination_file_name.parent.exists():
        destination_file_name.parent.mkdir(parents=True)

    print(
        f"IMAGE_PROXY {url=} --> "
        f"{origin_destination_file_name=} --> "
        f"{destination_file_name=}"
    )

    if destination_file_name.exists() and destination_file_name.stat().st_size > 0:
        print(f"IMAGE_PROXY: Destination file already exists: {destination_file_name}")
        destination_cache.append("hit")
    else:
        destination_cache.append("miss")

        def file_size(b: int) -> str:
            for unit in ["bytes", "KB", "MB", "GB"]:
                if b < 1024.0:
                    return f"{b:.2f} {unit}"
                b /= 1024.0
            return f"{b:.2f} TB"

        if (
            origin_destination_file_name.exists()
            and origin_destination_file_name.stat().st_size == 0
        ):
            origin_destination_file_name.unlink()

        if not origin_destination_file_name.exists():
            with open(origin_destination_file_name, "wb") as f:
                print("IMAGE_PROXY: FETCHING", url)
                response = requests.get(url)
                if response.status_code == 404:
                    print("IMAGE_PROXY WARNING: Image not found ", url)
                    return http.HttpResponseNotFound("Image not found")
                response.raise_for_status()
                f.write(response.content)
            print(
                f"IMAGE_PROXY: Fetched image from URL: {url} -> {origin_destination_file_name} "
                f"({file_size(origin_destination_file_name.stat().st_size)})"
            )
            destination_cache.append("fetched")

            # Now that it's been downloaded, the file extension might be a a lie
            if origin_destination_file_name.suffix in (".webp", ".jpeg", ".jpg"):
                file_type = _get_image_file_type(origin_destination_file_name)
                expected_file_type = _get_file_type_by_extension(
                    origin_destination_file_name.suffix
                )
                if expected_file_type is None:
                    raise ValueError(
                        f"Unknown file extension: {origin_destination_file_name.suffix}"
                    )

                if file_type != expected_file_type:
                    print(
                        f"IMAGE_PROXY WARNING: File type mismatch for {origin_destination_file_name}: "
                        f"expected {expected_file_type}, got {file_type}"
                    )
                    correct_extension = _get_extension_by_type(file_type)
                    if not correct_extension:
                        raise ValueError(
                            f"Cannot determine correct extension for file type: {file_type}"
                        )

                    new_name = origin_destination_file_name.with_suffix(
                        correct_extension
                    )
                    origin_destination_file_name.rename(new_name)
                    origin_destination_file_name = new_name

        if (
            origin_destination_file_name.name.endswith(".webp")
            or destination_file_extension in NO_CONVERT_FILE_EXTENSIONS
        ):
            print(
                "IMAGE_PROXY: Copying "
                f"{origin_destination_file_name} -> {destination_file_name}"
            )
            shutil.copy(origin_destination_file_name, destination_file_name)

            destination_cache.append("copied")
        else:
            try:
                print(
                    "\nCONVERTING",
                    origin_destination_file_name,
                    "TO",
                    destination_file_name,
                    "\n",
                )
                image = Image.open(origin_destination_file_name)
                image.save(destination_file_name, "webp", quality=99)
                print(
                    f"IMAGE_PROXY: Converted fetched image from URL: "
                    f"{origin_destination_file_name} -> {destination_file_name} "
                    f"({file_size(destination_file_name.stat().st_size)})"
                )
                destination_cache.append("converted")
            except UnidentifiedImageError as error:
                print(f"IMAGE_PROXY: UnidentifiedImageError: {error}")
                print(
                    f"IMAGE_PROXY: Failed to identify image from URL: {origin_destination_file_name} "
                    f"(file size: {file_size(origin_destination_file_name.stat().st_size)})"
                    if origin_destination_file_name.exists()
                    else " (file does not exist)"
                )
                origin_destination_file_name.unlink()
                return http.HttpResponseBadRequest("Bad image")

        origin_destination_file_name.unlink()

    if form.cleaned_data["redirect_to_file"]:
        response = http.HttpResponseRedirect(
            f"/image_proxy/{destination_file_name.relative_to(settings.IMAGE_PROXY_CACHE_ROOT)}"
        )
    else:
        response = http.HttpResponse()
        if destination_file_extension == "mp4":
            response["Content-Type"] = "video/mp4"
        elif destination_file_extension == "avif":
            response["Content-Type"] = "image/avif"
        else:
            response["Content-Type"] = "image/webp"
        with open(destination_file_name, "rb") as f:
            image_data = f.read()
        response.write(image_data)

    response["x-destination-cache"] = ", ".join(destination_cache)

    ttl = settings.DEBUG and 10 or 60 * 60 * 24
    patch_cache_control(response, max_age=ttl, public=True)

    return response


def fetch_image(url: str) -> bytes:
    response = requests.get(url)
    response.raise_for_status()
    return response.content


def _get_image_file_type(file_path: Path) -> str:
    try:
        image = Image.open(file_path)
        return image.format.lower()
    except UnidentifiedImageError:
        return "unknown"


def _get_file_type_by_extension(file_extension: str) -> str | None:
    extension_to_type = {
        ".jpg": "jpeg",
        ".jpeg": "jpeg",
        ".png": "png",
        ".webp": "webp",
        ".avif": "avif",
        ".mp4": "mp4",
    }
    return extension_to_type.get(file_extension.lower())


def _get_extension_by_type(file_type: str) -> str | None:
    type_to_extension = {
        "jpeg": ".jpg",
        "png": ".png",
        "webp": ".webp",
        "avif": ".avif",
        "mp4": ".mp4",
        "gif": ".gif",
    }
    return type_to_extension.get(file_type.lower())
