from django.conf import settings
from django.utils import timezone

from peterbecom.llmcalls.models import LLMCall
from peterbecom.llmcalls.tasks import execute_completion


def rewrite_comment(comment: str, oid: str):
    llm_call = get_llm_response_comment(comment, oid)
    if llm_call.status == "success":
        response = llm_call.response
        if "choices" in response and len(response["choices"]) > 0:
            choice = response["choices"][0]
            if "message" in choice and "content" in choice["message"]:
                return choice["message"]["content"]

    return None


def get_llm_response_comment(comment: str, oid: str):
    messages = []
    messages.append(
        {
            "role": "system",
            "content": "You are a helpful editor that reads blog post comments and corrects grammar and punctuations.",
        }
    )
    messages.append(
        {
            "role": "user",
            "content": "You have to look for common spelling mistakes, lack of spaces after full stops, incorrect capitalization.",
        }
    )
    # schema = {
    #     "type": "object",
    #     "properties": {
    #         "comment": {
    #             "type": "string",
    #             "description": "The rewritten comment with corrected grammar and punctuation.",
    #         },
    #     },
    # }

    # rendered_schema = json.dumps(schema, indent=4)
    # messages.append(
    #     {
    #         "role": "user",
    #         "content": f"""
    # Your job is to rewrite the comment without changing the meaning, but correcting any grammar and punctuation mistakes. You should also try to make the comment more readable and easier to understand.
    # Return your response in a JSON that conforms to the schema below.

    # ```json
    # {rendered_schema}
    # ```
    # """,
    #     }
    # )
    messages.append(
        {
            "role": "user",
            "content": """
    Your job is to rewrite the comment without changing the meaning, but correcting any grammar and punctuation mistakes. Only return the rewritten comment and nothing else.
    Avoid using Unicode quotation marks, use regular ASCII quotes instead.
    """,
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

    assert settings.OPENAI_API_KEY, "OPENAI_API_KEY must be set"

    MODEL = "gpt-5-mini"  # faster and more cost effective than gpt-5

    def create_and_start(attempts=0):
        llm_call = LLMCall.objects.create(
            status="progress",
            messages=messages,
            response={},
            model=MODEL,
            error=None,
            attempts=attempts,
            took_seconds=None,
            metadata={"comment": comment, "oid": oid},
        )

        execute_completion(llm_call.id)

        return llm_call

    query = LLMCall.objects.filter(
        model=MODEL,
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
