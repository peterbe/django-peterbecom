import hashlib
import json
import time

from crawlerdetect import CrawlerDetect
from django import forms, http
from django.conf import settings
from django.core.cache import cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from peterbecom.base.models import AnalyticsEvent, create_event
from peterbecom.base.utils import fake_ip_address


@csrf_exempt
@require_POST
def event(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return http.JsonResponse({"error": "invalid json"}, status=400)

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
        print("Analytics event form errors", form.errors)
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

    create_event(
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


def get_bot_analysis(ua: str) -> tuple[bool, str | None]:
    if not ua:
        return False, None
    cd = CrawlerDetect(user_agent=ua)
    return (cd.isCrawler(), cd.getMatches())
