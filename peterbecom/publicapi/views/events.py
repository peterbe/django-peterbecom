import hashlib
import json
import time
import uuid
from functools import lru_cache

from crawlerdetect import CrawlerDetect
from django import forms, http
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from peterbecom.base.batch_events import create_event_later
from peterbecom.base.models import AnalyticsEvent
from peterbecom.base.utils import fake_ip_address


@csrf_exempt
@require_POST
def event(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return http.JsonResponse({"error": "invalid json"}, status=400)
    except UnicodeDecodeError:
        print("WARNING, UnicodeDecodeError:", repr(request.body))
        return http.JsonResponse({"error": "invalid unicode"}, status=400)

    meta = data.get("meta") or {}
    if not isinstance(meta, dict):
        return http.JsonResponse({"error": "meta must be a dict"}, status=400)
    uuid = meta.get("uuid")
    url = meta.get("url")
    if url and len(url) > 500:
        url = url[: 500 - 3] + "..."
    denormalized = dict(
        data,
        uuid=uuid,
        url=url,
    )
    form = AnalyticsEventForm(denormalized)
    if not form.is_valid():
        return http.JsonResponse({"error": form.errors}, status=400)

    meta = form.cleaned_data.get("meta")
    url = form.cleaned_data["url"]
    uuid = form.cleaned_data["uuid"]
    type_ = form.cleaned_data["type"]
    data = form.cleaned_data.get("data") or {}

    if exists(uuid, type_, url, meta, data):
        return http.JsonResponse({"ok": True}, status=200)

    ip_address = request.headers.get("x-forwarded-for") or request.META.get(
        "REMOTE_ADDR"
    )
    if (
        ip_address == "127.0.0.1"
        and settings.DEBUG
        and request.get_host().endswith("127.0.0.1:8000")
    ):
        ip_address = fake_ip_address(str(time.time()))
    if ip_address:
        meta["ip_address"] = ip_address

    if meta.get("user_agent"):
        ua = meta["user_agent"].get("ua")
        if ua:
            is_bot, bot_agent = get_bot_analysis(ua)
            data["bot_agent"] = bot_agent
            data["is_bot"] = is_bot

    if type_ == "pageview" and data.get("pathname"):
        data["is_comment"] = (
            data["pathname"].startswith("/plog/") and "/comment/" in data["pathname"]
        )

    # create_event(
    #     type=type_,
    #     uuid=uuid,
    #     url=url,
    #     meta=meta,
    #     data=data,
    # )

    create_event_later(
        type=type_,
        uuid=uuid,
        url=url,
        meta=meta,
        data=data,
    )

    return http.JsonResponse({"ok": True}, status=201)


def exists(uuid: str, type_: str, url: str, meta: dict, data: dict, ttl_seconds=10):
    hash = _make_hash(uuid, type_, url, meta, data)
    cache_key = f"event-exits-{hash}"
    if cache.get(cache_key):
        return True
    cache.set(cache_key, True, ttl_seconds)
    return False


def _make_hash(uuid: str, type_: str, url: str, meta: dict, data: dict):
    h = hashlib.md5()
    h.update(str(uuid).encode())
    h.update(type_.encode())
    h.update(url.encode())
    for k, v in meta.items():
        if k in ("created", "performance"):
            continue
        h.update(f"{k}{v}".encode())
    for k, v in data.items():
        h.update(f"{k}{v}".encode())
    return h.hexdigest()


class AnalyticsEventForm(forms.ModelForm):
    class Meta:
        model = AnalyticsEvent
        fields = (
            "url",
            "uuid",
            "type",
            "meta",
            "data",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["data"].required = False

    def clean_type(self):
        type_ = self.cleaned_data["type"]
        if type_ not in AnalyticsEvent.VALID_TYPES:
            raise forms.ValidationError("Invalid event type")
        return type_


def get_bot_analysis(ua: str) -> tuple[bool, str | None]:
    if not ua:
        return False, None
    cd = CrawlerDetect(user_agent=ua)
    return (cd.isCrawler(), cd.getMatches())


@never_cache
def logo(request):
    referer = request.META.get("HTTP_REFERER") or ""
    query_string = request.META.get("QUERY_STRING") or ""
    set_cookie = ["logo-uuid", None]

    if referer and "ref" in query_string:
        uuid_ = request.COOKIES.get(set_cookie[0])
        if not uuid_:
            uuid_ = str(uuid.uuid4())
            set_cookie[1] = uuid_
        url = request.build_absolute_uri()
        meta = {}
        query = {}
        for key, value in request.GET.items():
            assert isinstance(value, str), type(value)
            if key in query:
                if not isinstance(query[key], list):
                    query[key] = [query[key]]
                query[key].append(value)
            else:
                query[key] = value
        data = {
            "ref": request.GET.get("ref"),
            "query": query,
            "referer": referer,
        }
        create_event_later(
            type="logo",
            uuid=uuid_,
            url=url,
            meta=meta,
            data=data,
        )

    response = http.HttpResponse(_get_image_file(), content_type="image/png")
    response["Content-Disposition"] = (
        f'inline; filename="{settings.LOGO_IMAGE_PATH.name}"'
    )
    if set_cookie[1]:
        response.set_cookie(
            set_cookie[0],
            uuid_,
            max_age=60 * 60 * 24 * 7,
            httponly=True,
        )

    return response


@lru_cache()
def _get_image_file():
    image_path = settings.LOGO_IMAGE_PATH
    if not image_path.exists():
        raise ImproperlyConfigured(f"logo image ({image_path}) does not exist")
    with open(image_path, "rb") as f:
        return f.read()
