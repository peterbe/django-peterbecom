import difflib
from html import escape

from peterbecom.api.views import api_superuser_required
from peterbecom.base.utils import json_response
from peterbecom.llmcalls.rewrite import rewrite_comment
from peterbecom.plog.models import BlogComment


@api_superuser_required
def comment_rewrite(request, oid):
    try:
        blogcomment = BlogComment.objects.get(oid=oid)
    except BlogComment.DoesNotExist:
        return json_response({"error": "Not found"}, status=404)

    if request.method == "DELETE":
        raise NotImplementedError("Not implemented yet")

    if request.method == "POST":
        raise NotImplementedError("Not implemented yet")

    context = {
        "rewritten": rewrite_comment(blogcomment.comment, blogcomment.oid),
        "error": None,
        "comment": blogcomment.comment,
        "html_diff": None,
    }
    if context["rewritten"]:
        context["html_diff"] = generate_inline_diff_html(
            blogcomment.comment, context["rewritten"]
        )

    return json_response(context)


def generate_inline_diff_html(text1: str, text2: str, with_color=False) -> str:
    """Generate HTML showing character-level differences"""
    s = difflib.SequenceMatcher(None, text1, text2)
    output: list[str] = []

    for opcode, i1, i2, j1, j2 in s.get_opcodes():
        if opcode == "equal":
            output.append(escape(text1[i1:i2]))
        elif opcode == "insert":
            if with_color:
                output.append(
                    f'<ins style="background-color: #90EE90">{escape(text2[j1:j2])}</ins>'
                )
            else:
                output.append(f'<ins class="diff--insert">{escape(text2[j1:j2])}</ins>')
        elif opcode == "delete":
            if with_color:
                output.append(
                    f'<del style="background-color: #FFB6C1">{escape(text1[i1:i2])}</del>'
                )
            else:
                output.append(f'<del class="diff--delete">{escape(text1[i1:i2])}</del>')
        elif opcode == "replace":
            if with_color:
                output.append(
                    f'<del style="background-color: #FFB6C1">{escape(text1[i1:i2])}</del>'
                )
                output.append(
                    f'<ins style="background-color: #90EE90">{escape(text2[j1:j2])}</ins>'
                )
            else:
                output.append(
                    f'<del class="diff--replace">{escape(text1[i1:i2])}</del>'
                )
                output.append(
                    f'<ins class="diff--replace">{escape(text2[j1:j2])}</ins>'
                )

    return "".join(output)
