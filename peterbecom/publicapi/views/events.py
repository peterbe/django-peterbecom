import json
import time

from django import forms
from django import http
from django.conf import settings
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
    denormalized = dict(
        data,
        uuid=uuid,
        url=url,
    )
    form = AnalyticsEventForm(denormalized)
    if not form.is_valid():
        return http.JsonResponse({"error": form.errors}, status=400)

    meta = form.cleaned_data.get("meta")
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
        type=form.cleaned_data["type"],
        uuid=uuid,
        url=url,
        meta=meta,
        data=form.cleaned_data.get("data") or {},
    )

    return http.JsonResponse({"ok": True}, status=201)


class AnalyticsEventForm(forms.ModelForm):
    class Meta:
        model = AnalyticsEvent
        fields = (
            "type",
            "meta",
            "data",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["data"].required = False
