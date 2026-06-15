import json

from django.utils import timezone
from django.views.decorators.http import require_POST

from peterbecom.api.forms import AICommentForm
from peterbecom.api.views import api_superuser_required
from peterbecom.base.utils import json_response
from peterbecom.llmcalls.models import LLMCall
from peterbecom.llmcalls.tasks import execute_completion
from peterbecom.plog.models import BlogComment
from peterbecom.settings.base import VALID_LLM_MODELS


@api_superuser_required
@require_POST
def suggest_ai_comment(request, oid):
    try:
        blogcomment = BlogComment.objects.get(oid=oid)
    except BlogComment.DoesNotExist:
        return json_response({"error": "Not found"}, status=404)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except json.decoder.JSONDecodeError:
        return json_response({"error": "Invalid JSON"}, status=400)
    form = AICommentForm(data, valid_models=VALID_LLM_MODELS)
    if not form.is_valid():
        return json_response({"errors": form.errors}, status=400)

    model = form.cleaned_data["model"]
    comment = form.cleaned_data["comment"]

    llm_call = get_llm_response_comment(comment, blogcomment.oid, model=model)

    comment_text = None
    if llm_call.status == "success":
        response = llm_call.response
        if llm_call.model.startswith("claude-"):
            for content in response["content"]:
                if content["type"] == "text":
                    comment_text = content["text"]
                    break

        if comment_text is None:
            raise ValueError("Could not extract comment text from response")

    context = {
        "comment": comment_text,
        "llm_call": {
            "took_seconds": llm_call.took_seconds,
            "status": llm_call.status,
            "error": llm_call.error,
            "model": llm_call.model,
            "created": llm_call.created,
        },
    }

    return json_response(context, status=201 if llm_call.status == "progress" else 200)


def get_llm_response_comment(
    comment: str,
    oid: str,
    model: str = VALID_LLM_MODELS[0],
    use_case="ai_comment_suggestion",
) -> LLMCall:

    messages = []
    system_prompt = """
    You are a reader of blog post comments where people write about seeking names of songs and their artists
    based on incomplete clues about music lyrics and what limited information they remember about the song.
    You are helpful and try to guess the song and artist based on the clues. You have a lot of knowledge about
    music and songs, but you don't have access to the internet.
    If you don't know the answer, say you don't know, but if you do know, give your best guess.
    """.strip()
    messages.append(
        {
            "role": "system",
            "content": system_prompt,
        }
    )

    messages.append(
        {
            "role": "user",
            "content": """
            Based on the clues, make a list of names of songs and their artists that you think the person is looking for.
            If you don't know, say you don't know.
            Do not suggest that are you are happy to refine your guess if the person can provide more clues.
            """.strip(),
        }
    )

    comment_escaped = comment.replace('"', '\\"').replace("\n", "\\n")

    messages.append(
        {
            "role": "user",
            "content": f"""
Here is the comment:

```
{comment_escaped}
```
    """.strip(),
        }
    )

    def create_and_start(attempts=0):
        llm_call = LLMCall.objects.create(
            use_case=use_case,
            status="progress",
            messages=messages,
            response={},
            model=model,
            error=None,
            attempts=attempts,
            took_seconds=None,
            metadata={"comment": comment, "oid": oid},
        )

        execute_completion(llm_call.id)

        return llm_call

    query = LLMCall.objects.filter(
        model=model,
        message_hash=LLMCall.make_message_hash(messages),
    )
    for llm_call in query.order_by("-created"):
        if llm_call.status in ("progress", "error"):
            age = timezone.now() - llm_call.created
            age_seconds = age.total_seconds()
            print(
                f"{llm_call!r} is in status {llm_call.status!r} "
                f"({age_seconds:.1f} seconds old)"
            )
            if age_seconds > 60 * 5:
                if llm_call.attempts <= 3:
                    return create_and_start(attempts=llm_call.attempts + 1)
                else:
                    print(f"Giving up on {llm_call!r} after 3 attempts")

        return llm_call

    return create_and_start()
