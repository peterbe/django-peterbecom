import json

from django import forms
from django import http
from django.views.decorators.csrf import csrf_exempt

from peterbecom.base.models import AnalyticsEvent


@csrf_exempt
def events(request):
    data = json.loads(request.body.decode("utf-8"))

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

    AnalyticsEvent.objects.create(
        type=form.cleaned_data["type"],
        uuid=uuid,
        url=url,
        meta=form.cleaned_data.get("meta"),
        data=form.cleaned_data.get("data") or {},
    )

    return http.JsonResponse({"ok": True})


class AnalyticsEventForm(forms.ModelForm):
    class Meta:
        model = AnalyticsEvent
        fields = (
            "type",
            "meta",
            "data",
        )
