import time

import litellm
from django.conf import settings
from huey.contrib.djhuey import task

from peterbecom.llmcalls.models import LLMCall


@task()
def execute_completion(llm_call_id):
    llm_call = LLMCall.objects.get(id=llm_call_id)

    print("EXECUTING....")
    from pprint import pprint

    pprint(llm_call.messages)

    t0 = time.time()

    response = litellm.completion(
        model=llm_call.model,
        api_key=settings.OPENAI_API_KEY,
        messages=llm_call.messages,
        # temperature=0,
        # response_format={"type": "json_object"},
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
