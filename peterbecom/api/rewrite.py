import difflib
from html import escape

from peterbecom.api.views import api_superuser_required
from peterbecom.base.utils import json_response
from peterbecom.llmcalls.rewrite import get_llm_response_comment
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

    llm_call = get_llm_response_comment(blogcomment.comment, blogcomment.oid)
    rewritten = None
    if llm_call.status == "success":
        response = llm_call.response
        if "choices" in response and len(response["choices"]) > 0:
            choice = response["choices"][0]
            if "message" in choice and "content" in choice["message"]:
                rewritten = choice["message"]["content"]

    context = {
        "rewritten": rewritten,
        "llm_call": {
            "took_seconds": llm_call.took_seconds,
            "status": llm_call.status,
            "error": llm_call.error,
            "model": llm_call.model,
        },
        "comment": blogcomment.comment,
        "html_diff": None,
    }
    if context["rewritten"]:
        context["html_diff"] = generate_inline_diff_html(
            blogcomment.comment, context["rewritten"]
        )

    return json_response(context, status=201 if llm_call.status == "progress" else 200)


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
