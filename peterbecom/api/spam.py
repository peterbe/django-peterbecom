import json

from django import http

from peterbecom.api.forms import SpamCommentPatternForm, SpamCommentSignatureForm
from peterbecom.base.utils import json_response
from peterbecom.plog.models import SpamCommentPattern, SpamCommentSignature


def patterns(request):
    if request.method == "DELETE":
        id = request.GET.get("id")
        if not id:
            return json_response({"error": "No ID"}, status=400)
        for signature in SpamCommentPattern.objects.filter(id=id):
            signature.delete()
            return json_response({"ok": True})
        else:
            return json_response({"error": "Not found"}, status=404)

    if request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
        except json.decoder.JSONDecodeError:
            return json_response({"error": "Invalid JSON"}, status=400)
        form = SpamCommentPatternForm(data)
        if form.is_valid():
            SpamCommentPattern.objects.create(
                pattern=form.cleaned_data["pattern"],
                is_regex=form.cleaned_data["is_regex"],
                is_url_pattern=form.cleaned_data["is_url_pattern"],
            )
            return json_response({"ok": True})
        else:
            return json_response({"errors": form.errors}, status=400)

    context = {"patterns": []}
    qs = SpamCommentPattern.objects.all().order_by("-modify_date")
    for signature in qs.values():
        context["patterns"].append(
            {
                "id": signature["id"],
                "pattern": signature["pattern"],
                "is_regex": signature["is_regex"],
                "is_url_pattern": signature["is_url_pattern"],
                "kills": signature["kills"],
                "add_date": signature["add_date"],
                "modify_date": signature["modify_date"],
            }
        )
    return http.JsonResponse(context)


def signatures(request):
    if request.method == "DELETE":
        id = request.GET.get("id")
        if not id:
            return json_response({"error": "No ID"}, status=400)
        for signature in SpamCommentSignature.objects.filter(id=id):
            signature.delete()
            return json_response({"ok": True})
        else:
            return json_response({"error": "Not found"}, status=404)

    if request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
        except json.decoder.JSONDecodeError:
            return json_response({"error": "Invalid JSON"}, status=400)
        form = SpamCommentSignatureForm(data)
        if form.is_valid():
            name = form.cleaned_data["name"]
            if not name and form.cleaned_data["name_null"]:
                name = None
            email = form.cleaned_data["email"]
            if not email and form.cleaned_data["email_null"]:
                email = None
            SpamCommentSignature.objects.create(
                name=name,
                email=email,
            )
            return json_response({"ok": True})
        else:
            return json_response({"errors": form.errors}, status=400)

    context = {"signatures": []}
    qs = SpamCommentSignature.objects.all().order_by("-modify_date")
    for signature in qs.values():
        context["signatures"].append(
            {
                "id": signature["id"],
                "name": signature["name"],
                "email": signature["email"],
                "kills": signature["kills"],
                "add_date": signature["add_date"],
                "modify_date": signature["modify_date"],
            }
        )
    return http.JsonResponse(context)
