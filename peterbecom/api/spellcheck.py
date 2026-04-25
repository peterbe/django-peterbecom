import datetime
import json
import time
from functools import wraps

from django import http
from django.utils import timezone
from django.views.decorators.http import require_POST

from peterbecom.api.rewrite import generate_inline_diff_html
from peterbecom.base.utils import json_response
from peterbecom.llmcalls.models import LLMCall
from peterbecom.llmcalls.tasks import execute_completion


def api_superuser_required(view_func):
    """Decorator that will return a 403 JSON response if the user
    is *not* a superuser.
    Use this decorator *after* others like api_login_required.
    """

    @wraps(view_func)
    def inner(request, *args, **kwargs):
        if not request.user.is_superuser:
            error_msg = "Must be superuser to access this view."
            # raise PermissionDenied(error_msg)
            return http.JsonResponse({"error": error_msg}, status=403)
        return view_func(request, *args, **kwargs)

    return inner


@api_superuser_required
@require_POST
def spellcheck_markdown(request):
    context = {
        "spellcheck": [],
        "errors": [],
        "metadata": {
            "took_seconds": None,
        },
    }

    t0 = time.time()
    try:
        post_data = json.loads(request.body.decode("utf-8"))
        markdown_text = post_data["markdown"]
        paragraphs = spellcheck_markdown_text(markdown_text)
        context["spellcheck"] = paragraphs
    except json.JSONDecodeError:
        return json_response(context, status=400)

    context["metadata"]["took_seconds"] = time.time() - t0
    return json_response(context)


def spellcheck_markdown_text(markdown_text):
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
        llm_call = start_spellcheck(task["before"])
        llm_calls.append((task, llm_call))

    start_time = time.time()
    time.sleep(3)
    while True:
        all_done = True
        for task, llm_call in llm_calls:
            # print("TASK:", task)
            llm_call.refresh_from_db()
            # print("LLMCALL:", llm_call)
            if llm_call.status == "success":
                # print("SUCCESS! Response...:")
                # from pprint import pprint

                # pprint(llm_call.response)
                task["after"] = (
                    llm_call.response.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )
                task["total_time"] = time.time() - start_time
                task["html_diff"] = generate_inline_diff_html(
                    task["before"], task["after"]
                )
                task["error"] = None

            elif llm_call.status == "error":
                task["after"] = task["before"]
                task["error"] = True
                task["total_time"] = time.time() - start_time
                task["html_diff"] = None
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
        time.sleep(5)

    return tasks


def start_spellcheck(paragraph, model="gpt-5"):
    last_hour = timezone.now() - datetime.timedelta(hours=1)
    recent_candidates = LLMCall.objects.filter(
        model=model,
        status__in=["progress", "success"],
        error__isnull=True,
        created__gt=last_hour,
    )
    # print(recent_candidates)
    for candidate in recent_candidates:
        # print("CANDIDATE?", repr(candidate))
        # print("CANDIDATE PARAGRAPH?", repr(candidate.metadata.get("paragraph")))
        # print("THIS PARAGRAPH?", repr(paragraph))
        if candidate.metadata.get("paragraph") == paragraph:
            print("Found recent candidate with same paragraph, reusing it...")
            return candidate

    print("No recent candidate found, creating a new one...")

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

    paragraph_escaped = paragraph.replace('"', '\\"').replace("\n", "\\n")

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

    def create_and_start(attempts=0):
        llm_call = LLMCall.objects.create(
            status="progress",
            messages=messages,
            response={},
            model=model,
            error=None,
            attempts=attempts,
            took_seconds=None,
            metadata={"paragraph": paragraph},
        )

        execute_completion(llm_call.id)

        return llm_call

    return create_and_start()
