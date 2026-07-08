from django.urls import reverse

from peterbecom.llmcalls.models import LLMCall


def test_empty(admin_client):
    url = reverse("api:llmcalls")
    response = admin_client.get(url)
    assert response.status_code == 200
    assert response.json() == {
        "count": 0,
        "calls": [],
        "aggregates": {"model": {}, "status": {}, "use_case": {}},
        "metadata": {
            "batch_size": 100,
            "model": "",
            "status": "",
            "use_case": "",
        },
    }


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


def test_aggregates_and_filtering(admin_client):
    messages = [
        {"role": "system", "content": "bla"},
        {"role": "user", "content": "Ble Ble"},
    ]
    LLMCall.objects.create(
        status="success",
        messages=messages,
        message_hash=LLMCall.make_message_hash(messages),
        temperature=0,
        response={"choices": [{"message": {"content": "Hi"}}]},
        model="gpt-3.5-turbo",
        took_seconds=1.23,
        use_case="bar",
    )
    LLMCall.objects.create(
        status="success",
        messages=messages,
        message_hash=LLMCall.make_message_hash(messages),
        temperature=0,
        response={"choices": [{"message": {"content": "Hi"}}]},
        model="gpt-3.5-turbo",
        took_seconds=1.23,
        use_case="foo",
    )
    LLMCall.objects.create(
        status="progress",
        messages=messages,
        message_hash=LLMCall.make_message_hash(messages),
        temperature=0,
        response={"choices": [{"message": {"content": "Hi"}}]},
        model="gpt-3.5-turbo",
        took_seconds=1.23,
        use_case="foo",
    )
    LLMCall.objects.create(
        status="success",
        messages=messages,
        message_hash=LLMCall.make_message_hash(messages),
        temperature=0,
        response={"choices": [{"message": {"content": "Hi"}}]},
        model="claude-stable-100k",
        took_seconds=1.23,
        use_case="foo",
    )
    url = reverse("api:llmcalls")
    response = admin_client.get(url)
    assert response.status_code == 200
    assert response.json()["count"] == 4
    aggregates = response.json()["aggregates"]
    assert aggregates == {
        "status": {"success": 3, "progress": 1},
        "model": {"claude-stable-100k": 1, "gpt-3.5-turbo": 3},
        "use_case": {"foo": 3, "bar": 1},
    }

    filter_response = admin_client.get(url, {"status": "success"})
    assert filter_response.status_code == 200
    assert filter_response.json()["count"] == 3
    assert filter_response.json()["aggregates"] == response.json()["aggregates"]

    filter_response = admin_client.get(
        url, {"status": "success", "model": "gpt-3.5-turbo"}
    )
    assert filter_response.status_code == 200
    assert filter_response.json()["count"] == 2
    assert filter_response.json()["aggregates"] == response.json()["aggregates"]

    filter_response = admin_client.get(
        url, {"status": "success", "model": "gpt-3.5-turbo", "use_case": "foo"}
    )
    assert filter_response.status_code == 200
    assert filter_response.json()["count"] == 1
    assert filter_response.json()["aggregates"] == response.json()["aggregates"]


def test_valid_llmcall_models(admin_client, settings):
    settings.VALID_LLM_MODELS = ("foo", "bar")
    settings.VALID_LLM_SUGGEST_COMMENT_MODELS = ("foo",)
    url = reverse("api:valid_llmcall_models")
    response = admin_client.get(url)
    assert response.status_code == 200
    data = response.json()
    assert set(data["models"]) == set(["foo", "bar"])

    response = admin_client.get(url, {"use_case": "ai-suggest-comment"})
    assert response.status_code == 200
    data = response.json()
    assert set(data["models"]) == set(["foo"])


def test_valid_llmcall_use_cases(admin_client):
    messages = [
        {"role": "system", "content": "bla"},
        {"role": "user", "content": "Ble Ble"},
    ]
    LLMCall.objects.create(
        status="success",
        messages=messages,
        message_hash=LLMCall.make_message_hash(messages),
        temperature=0,
        response={"choices": [{"message": {"content": "Hi"}}]},
        model="claude-stable-100k",
        took_seconds=1.23,
        use_case="fooing",
    )
    LLMCall.objects.create(
        status="success",
        messages=messages,
        message_hash=LLMCall.make_message_hash(messages),
        temperature=0,
        response={"choices": [{"message": {"content": "Hi"}}]},
        model="claude-stable-100k",
        took_seconds=1.23,
        use_case="baring",
    )
    messages.append({"role": "user", "content": "Blue"})
    LLMCall.objects.create(
        status="success",
        messages=messages,
        message_hash=LLMCall.make_message_hash(messages),
        temperature=0,
        response={"choices": [{"message": {"content": "Ho"}}]},
        model="claude-stable-100k",
        took_seconds=1,
        use_case="baring",
    )

    url = reverse("api:valid_llmcall_use_cases")
    response = admin_client.get(url)
    assert response.status_code == 200
    data = response.json()
    assert data["use_cases"] == [
        {"use_case": "baring", "count": 2},
        {"use_case": "fooing", "count": 1},
    ]
