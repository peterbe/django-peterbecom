import json
import re

from django import http
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from peterbecom.api.forms import SpamCommentPatternForm, SpamCommentSignatureForm
from peterbecom.api.views import api_superuser_required
from peterbecom.base.utils import json_response
from peterbecom.plog.models import BlogComment, SpamCommentPattern, SpamCommentSignature


@api_superuser_required
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


@api_superuser_required
@require_POST
def execute_pattern(request, id):
    pattern = get_object_or_404(SpamCommentPattern, id=id)

    executions = []
    LIMIT = 1000
    context = {
        "OK": True,
        "limit": LIMIT,
    }
    qs = BlogComment.objects.all().order_by("-add_date")

    for comment, approved in qs.values_list("comment", "approved")[:LIMIT]:
        if pattern.pattern in comment:
            executions.append(
                {
                    "matched": True,
                    "approved": approved,
                    "regex": False,
                }
            )
        elif pattern.is_regex and matched_regex(pattern.pattern, comment):
            executions.append(
                {
                    "matched": True,
                    "approved": approved,
                    "regex": True,
                }
            )
        else:
            executions.append(
                {
                    "matched": False,
                    "approved": approved,
                    "regex": None,
                }
            )
    context = {
        "limit": LIMIT,
        "executions": executions,
    }

    return json_response(context)


def matched_regex(regex_str: str, text: str):
    for _ in re.findall(regex_str, text):
        return True

    return False
