import base64
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from peterbecom.llmcalls.models import LLMCall
from peterbecom.llmcalls.tasks import execute_completion
from peterbecom.settings.base import VALID_LLM_MODELS


def get_image_transcript(image_path: Path):
    llm_call = get_llm_response_image_transcript(image_path)
    if llm_call.status == "success":
        response = llm_call.response
        if "choices" in response and len(response["choices"]) > 0:
            choice = response["choices"][0]
            if "message" in choice and "content" in choice["message"]:
                return choice["message"]["content"]

    return None


def get_llm_response_image_transcript(
    image_path: Path,
    # model="claude-sonnet-5-5",
    model: str = VALID_LLM_MODELS[0],
    use_case="chiveproxy_image_transcript",
) -> LLMCall:
    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    if image_path.suffix.lower() == ".webp":
        media_type = "image/webp"
    elif image_path.suffix.lower() == ".png":
        media_type = "image/png"
    elif image_path.suffix.lower() == ".jpg" or image_path.suffix.lower() == ".jpeg":
        media_type = "image/jpeg"
    else:
        raise ValueError(f"Unsupported image format: {image_path.suffix}")

    messages = (
        [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": "Extract all text from this image exactly as it appears. "
                        "Preserve line breaks and layout where possible. "
                        "Output only the extracted text, with no commentary.",
                    },
                ],
            }
        ],
    )
    assert settings.ANTHROPIC_API_KEY, "ANTHROPIC_API_KEY must be set"

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
            metadata={"image_path": str(image_path)},
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
