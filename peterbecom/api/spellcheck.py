import datetime
import json
import time

from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from peterbecom.api.view_utils import api_superuser_required
from peterbecom.base.utils import json_response
from peterbecom.llmcalls.models import LLMCall
from peterbecom.llmcalls.tasks import execute_completion
from peterbecom.plog.models import (
    BlogItem,
)


@api_superuser_required
@require_POST
def spellcheck_markdown(request, oid):
    blogitem = get_object_or_404(BlogItem, oid=oid)
    context = {
        "spellcheck": [],
        "errors": [],
        "metadata": {
            "took_seconds": None,
            "blogitem_oid": oid,
        },
    }

    t0 = time.time()
    try:
        post_data = json.loads(request.body.decode("utf-8"))
        markdown_text = post_data["markdown"]
        paragraphs = spellcheck_markdown_text(markdown_text, blogitem)
        context["spellcheck"] = paragraphs
    except json.JSONDecodeError:
        return json_response(context, status=400)

    context["metadata"]["took_seconds"] = time.time() - t0
    return json_response(context)


def spellcheck_markdown_text(
    markdown_text, blogitem: BlogItem, model="claude-opus-4-8"
):
    # Split the markdown text into paragraphs based on double newlines
    paragraphs = markdown_text.split("\n\n")

    tasks = []
    in_code_block = False
    for i, paragraph in enumerate(paragraphs):
        if paragraph.strip().startswith("```"):
            in_code_block = True
        elif paragraph.strip().endswith("```"):
            in_code_block = False
        elif paragraph.strip().startswith("<") and paragraph.strip().endswith(">"):
            continue
        elif len(paragraph.strip().split()) < 5:
            continue
        elif not in_code_block:
            tasks.append(
                {
                    "index": i,
                    "before": paragraph.strip(),
                    "after": "",
                }
            )

    llm_calls = []
    for task in tasks:
        if llm_call := find_llm_call_for_paragraph(
            task["before"], blogitem, model=model
        ):
            llm_calls.append((task, llm_call))
        else:
            llm_calls.append(
                (task, start_spellcheck(task["before"], blogitem, model=model))
            )

    if not all([llm_call.status == "success" for _, llm_call in llm_calls]):
        # At least one was not previously found
        time.sleep(2)

    start_time = time.time()
    while True:
        all_done = True
        for task, llm_call in llm_calls:
            if llm_call.status == "progress":
                llm_call.refresh_from_db()

            if llm_call.status == "success":
                if llm_call.model.startswith("claude"):
                    for content in llm_call.response["content"]:
                        if content["type"] == "text":
                            text_content = content["text"]
                            break

                else:
                    text_content = (
                        llm_call.response.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "")
                    )
                task["after"] = text_content
                task["total_time"] = time.time() - start_time

                task["error"] = None

            elif llm_call.status == "error":
                task["after"] = task["before"]
                task["error"] = True
                task["total_time"] = time.time() - start_time
            else:
                all_done = False

        if all_done:
            break

        total_time = time.time() - start_time
        if total_time > 120:
            # If it takes more than 2 minutes, just give up and use the original text
            for task, llm_call in llm_calls:
                if llm_call.status == "progress":
                    task["after"] = task["before"]
            break
        time.sleep(3)

    return tasks


def find_llm_call_for_paragraph(paragraph: str, blogitem: BlogItem, model="gpt-5"):
    last_hour = timezone.now() - datetime.timedelta(hours=1)
    messages = _get_spellcheck_messages(paragraph, model=model)
    message_hash = LLMCall.make_message_hash(messages)
    recent_candidates = LLMCall.objects.filter(
        model=model,
        status__in=["progress", "success"],
        error__isnull=True,
        created__gt=last_hour,
        metadata__blogitem_oid=blogitem.oid,
        message_hash=message_hash,
    )
    for candidate in recent_candidates:
        if candidate.metadata.get("paragraph") == paragraph:
            return candidate


def start_spellcheck(paragraph: str, blogitem: BlogItem, model="gpt-5"):

    messages = _get_spellcheck_messages(paragraph, model=model)

    def create_and_start(attempts=0):
        llm_call = LLMCall.objects.create(
            use_case="admin_spellcheck_markdown",
            status="progress",
            messages=messages,
            response={},
            model=model,
            error=None,
            attempts=attempts,
            took_seconds=None,
            metadata={"paragraph": paragraph, "blogitem_oid": blogitem.oid},
        )

        execute_completion(llm_call.id)

        return llm_call

    return create_and_start()


def _get_spellcheck_messages(paragraph: str, model="gpt-5"):
    messages = []
    messages.append(
        {
            "role": "system",
            "content": (
                "You are a helpful editor that corrects a paragraph of Markdown text."
            ),
        }
    )
    messages.append(
        {
            "role": "user",
            "content": (
                "You have to look for common spelling mistakes, lack of spaces "
                "after full stops, incorrect capitalization. Also look for "
                "grammar errors and awkward phrasing."
            ),
        }
    )

    messages.append(
        {
            "role": "user",
            "content": "Your job is to rewrite the paragraph without changing "
            "the meaning, but correcting any grammar and punctuation mistakes. "
            "Only return the rewritten paragraph and nothing else. "
            "Avoid using Unicode quotation marks, "
            "use regular ASCII quotes instead."
            "".strip(),
        }
    )

    if model.startswith("claude"):
        paragraph_escaped = paragraph.replace('"', '\\"')

    else:
        paragraph_escaped = paragraph.replace('"', '\\"').replace("\n", "\\n")

    if model.startswith("claude"):
        messages.append(
            {
                "role": "user",
                "content": f"""
        Here is the paragraph:

        {paragraph_escaped}
        """.strip(),
            }
        )
    else:
        messages.append(
            {
                "role": "user",
                "content": f"""
        Here is the paragraph:

        ```
        {paragraph_escaped}
        ```
        """.strip(),
            }
        )

    return messages
