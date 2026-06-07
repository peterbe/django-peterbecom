import time

import litellm
import anthropic
from django.conf import settings
from huey.contrib.djhuey import task

from peterbecom.llmcalls.models import LLMCall


@task()
def execute_completion(llm_call_id, timeout=60):
    _execute_completion(llm_call_id, timeout=timeout)


def _execute_completion(llm_call_id, timeout=60):
    llm_call = LLMCall.objects.get(id=llm_call_id)

    print("EXECUTING....")
    from pprint import pprint

    pprint(llm_call.messages)

    t0 = time.time()
    if llm_call.model.startswith("claude"):
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        messages = []
        system_prompt = None
        for message in llm_call.messages:
            if message["role"] == "system":
                if system_prompt is not None:
                    raise ValueError("Multiple system prompts not supported")
                system_prompt = message["content"]
            else:
                messages.append(message)

        response = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=1000,  # necessary??
            system=system_prompt,
            messages=messages,
        )

    else:
        response = litellm.completion(
            model=llm_call.model,
            api_key=settings.OPENAI_API_KEY,
            messages=llm_call.messages,
            # temperature=0,
            # response_format={"type": "json_object"},
            timeout=timeout,
        )
    try:
        print(llm_call, "succeeded")
        LLMCall.objects.filter(id=llm_call_id).update(
            status="success",
            response=response.to_dict(),
            took_seconds=time.time() - t0,
        )

    except Exception as e:
        print(llm_call, "errored", e)
        LLMCall.objects.filter(id=llm_call_id).update(
            status="error",
            error=str(e),
            took_seconds=time.time() - t0,
        )
