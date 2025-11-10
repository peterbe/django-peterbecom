import time

import litellm
from django.conf import settings

from peterbecom.llmcalls.models import LLMCall


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

    MODEL = "gpt-5"

    query = LLMCall.objects.filter(
        model=MODEL, message_hash=LLMCall.make_message_hash(messages)
    )
    for llm_call in query.order_by("-created"):
        return llm_call

    llm_call = LLMCall.objects.create(
        status="progress",
        messages=messages,
        response={},
        model=MODEL,
        error=None,
        took_seconds=None,
        metadata={
            "comment": comment,
            "oid": oid,
        },
    )

    # print("EXECUTING....")
    # from pprint import pprint

    # pprint(messages)

    response = litellm.completion(
        # model="azure/gpt-4o",
        # model="gpt-4o",
        # model="gpt-5",
        model=MODEL,
        api_key=settings.OPENAI_API_KEY,
        messages=messages,
        # temperature=0,
        # response_format={"type": "json_object"},
    )
    t0 = time.time()
    try:
        llm_call.status = "success"
        llm_call.response = response.to_dict()
        llm_call.took_seconds = time.time() - t0
        llm_call.save()

    except Exception as e:
        llm_call.status = "error"
        llm_call.error = str(e)
        llm_call.took_seconds = time.time() - t0
        llm_call.save()
    return llm_call
