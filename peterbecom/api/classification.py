import json

from django.db.models import Count

from peterbecom.api.forms import BlogCommentClassificationForm
from peterbecom.api.views import api_superuser_required
from peterbecom.base.utils import json_response
from peterbecom.plog.models import BlogComment, BlogCommentClassification


@api_superuser_required
def comment_classify(request, oid):
    try:
        blogcomment = BlogComment.objects.get(oid=oid)
    except BlogComment.DoesNotExist:
        return json_response({"error": "Not found"}, status=404)

    if request.method == "DELETE":
        id = request.GET.get("id")
        if not id:
            return json_response({"error": "No ID"}, status=400)
        for obj in BlogCommentClassification.objects.filter(
            blogcomment=blogcomment, id=id
        ):
            obj.delete()
            return json_response({"ok": True})
        else:
            return json_response({"error": "Not found"}, status=404)

    if request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
        except json.decoder.JSONDecodeError:
            return json_response({"error": "Invalid JSON"}, status=400)
        form = BlogCommentClassificationForm(data)
        if form.is_valid():
            qs = BlogCommentClassification.objects.filter(
                blogcomment=blogcomment,
                classification=form.cleaned_data["classification"],
            )
            for _ in qs:
                return json_response({"ok": True}, status=200)

            BlogCommentClassification.objects.create(
                blogcomment=blogcomment,
                classification=form.cleaned_data["classification"],
                text=form.cleaned_data["text"],
            )
            return json_response({"ok": True}, status=201)
        else:
            return json_response({"errors": form.errors}, status=400)

    context = {"classification": None, "choices": []}

    for obj in BlogCommentClassification.objects.filter(blogcomment=blogcomment):
        context["classification"] = {
            "id": obj.id,
            "classification": obj.classification,
            "text": obj.text,
            "add_date": obj.add_date,
            "modify_date": obj.modify_date,
        }

    for x in (
        BlogCommentClassification.objects.values("classification")
        .order_by("classification")
        .annotate(count=Count("classification"))
    ):
        context["choices"].append({"value": x["classification"], "count": x["count"]})

    return json_response(context)
