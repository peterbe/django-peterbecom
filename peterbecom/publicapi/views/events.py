import json
import time
from datetime import timedelta

from django import forms, http
from django.conf import settings
from django.utils import timezone
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

    uuid = data.get("meta", {}).get("uuid")
    url = data.get("meta", {}).get("url")
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

    recently = timezone.now() - timedelta(seconds=10)
    qs = AnalyticsEvent.objects.filter(
        uuid=uuid, type=type_, url=url, created__gt=recently
    )
    for k, v in meta.items():
        if k in ("created", "performance"):
            continue
        qs = qs.filter(**{f"meta__{k}": v})

    for k, v in data.items():
        qs = qs.filter(**{f"data__{k}": v})

    for _ in qs.order_by("-created"):
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

    create_event(
        type=type_,
        uuid=uuid,
        url=url,
        meta=meta,
        data=data,
    )

    return http.JsonResponse({"ok": True}, status=201)


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
