import json

import backoff
from django import forms
from django import http
from django.db.utils import InterfaceError
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from peterbecom.base.models import AnalyticsEvent


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

    create_event(
        type=form.cleaned_data["type"],
        uuid=uuid,
        url=url,
        meta=form.cleaned_data.get("meta"),
        data=form.cleaned_data.get("data") or {},
    )

    return http.JsonResponse({"ok": True}, status=201)


@backoff.on_exception(backoff.expo, InterfaceError, max_time=10)
def create_event(type: str, uuid: str, url: str, meta: dict, data: dict):
    AnalyticsEvent.objects.create(
        type=type,
        uuid=uuid,
        url=url,
        meta=meta,
        data=data,
    )


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
