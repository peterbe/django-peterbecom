import json

from django.views.decorators.http import require_http_methods

from peterbecom.api.forms import BlogCommentClassificationForm
from peterbecom.base.utils import json_response
from peterbecom.plog.models import BlogComment, BlogCommentClassification


@require_http_methods(["DELETE", "POST"])
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

    raise Exception("Should never get here")
