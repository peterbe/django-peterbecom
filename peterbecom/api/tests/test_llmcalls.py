from django.urls import reverse

from peterbecom.llmcalls.models import LLMCall


def test_empty(admin_client):
    url = reverse("api:llmcalls")
    response = admin_client.get(url)
    assert response.status_code == 200
    assert response.json() == {"count": 0, "calls": []}


def test_ok(admin_client):
    messages = [
        {"role": "system", "content": "bla"},
        {"role": "user", "content": "Ble Ble"},
    ]
    llm_call = LLMCall.objects.create(
        status="success",
        messages=messages,
        message_hash=LLMCall.make_message_hash(messages),
        temperature=0,
        response={"choices": [{"message": {"content": "Hi"}}]},
        model="gpt-3.5-turbo",
        took_seconds=1.23,
        use_case="testing",
    )
    url = reverse("api:llmcalls")
    response = admin_client.get(url)
    assert response.status_code == 200
    assert response.json()["count"] == 1
    calls = response.json()["calls"]
    first = calls[0]
    assert first == {
        "attempts": 0,
        "created": first["created"],
        "error": None,
        "id": llm_call.id,
        "message_hash": llm_call.message_hash,
        "messages": messages,
        "metadata": {},
        "model": "gpt-3.5-turbo",
        "modified": first["modified"],
        "response": {"choices": [{"message": {"content": "Hi"}}]},
        "status": "success",
        "temperature": 0,
        "took_seconds": 1.23,
        "use_case": "testing",
    }
