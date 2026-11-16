import json

from django import forms, http

from peterbecom.api.views import api_superuser_required
from peterbecom.base.utils import json_response
from peterbecom.chiveproxy.models import BannedUrlPattern


class BannedUrlPatternForm(forms.ModelForm):
    class Meta:
        model = BannedUrlPattern
        fields = ("pattern", "is_regex", "case_insensitive")


@api_superuser_required
def banned_url_patterns(request):
    if request.method == "DELETE":
        id = request.GET.get("id")
        if not id:
            return json_response({"error": "No ID"}, status=400)
        for signature in BannedUrlPattern.objects.filter(id=id):
            signature.delete()
            return json_response({"ok": True})
        return json_response({"error": "Not found"}, status=404)

    if request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
        except json.decoder.JSONDecodeError:
            return json_response({"error": "Invalid JSON"}, status=400)
        form = BannedUrlPatternForm(data)
        if form.is_valid():
            BannedUrlPattern.objects.create(
                pattern=form.cleaned_data["pattern"],
                is_regex=form.cleaned_data["is_regex"],
                case_insensitive=form.cleaned_data["case_insensitive"],
            )
            return json_response({"ok": True}, status=201)
        else:
            return json_response({"errors": form.errors}, status=400)

    context = {"patterns": []}
    qs = BannedUrlPattern.objects.all().order_by("-modified")
    for entry in qs.values():
        context["patterns"].append(entry)
    return http.JsonResponse(context)
