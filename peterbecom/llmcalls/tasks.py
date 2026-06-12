import time
from datetime import timedelta

import anthropic
import openai
import litellm
from django.conf import settings
from django.utils import timezone
from huey import crontab
from huey.contrib.djhuey import periodic_task, task

from peterbecom.llmcalls.models import LLMCall


@periodic_task(crontab(hour="*", minute="0"))
def clean_stale_llm_calls():
    stale_after = timezone.now() - timedelta(hours=24)
    in_progress = LLMCall.objects.filter(status="progress", modified__lt=stale_after)
    stale_count = in_progress.count()
    print(f"LLMCalls cleanup: Found {stale_count} stale LLM calls still in progress")
    if stale_count:
        in_progress.delete()

    very_old = timezone.now() - timedelta(days=365)
    old_calls = LLMCall.objects.filter(created__lt=very_old)
    old_count = old_calls.count()
    print(f"LLMCalls cleanup: Found {old_count} very old LLM calls")
    if old_count:
        old_calls.delete()


@task()
def execute_completion(llm_call_id, timeout=60):
    _execute_completion(llm_call_id, timeout=timeout)


def _execute_completion(llm_call_id, timeout=60):
    llm_call = LLMCall.objects.get(id=llm_call_id)

    print(f"Executing LLMCall {llm_call!r}")

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

    elif llm_call.model.startswith("openai-"):
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.responses.create(
            model=llm_call.model.replace("openai-", ""),
            input=llm_call.messages,
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
