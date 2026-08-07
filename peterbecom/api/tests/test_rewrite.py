import json

import anthropic
import openai
import pytest
from django.urls import reverse
from django.utils import timezone

from peterbecom.plog.models import (
    BlogComment,
    BlogItem,
)


class Completion:
    def __init__(self, response):
        self._response = response

    def to_dict(self):
        return self._response


@pytest.mark.django_db
def test_rewrite_openai(admin_client, monkeypatch):

    class FakeResponsesAPI:
        def create(self, **kwargs):
            return Completion(
                {
                    "id": "chatcmpl-E9aBlvFmVg8RKOh4NFAoYR9aDijRC",
                    "model": "gpt-5-2025-08-07",
                    "usage": {
                        "total_tokens": 854,
                        "prompt_tokens": 157,
                        "completion_tokens": 697,
                        "prompt_tokens_details": {
                            "audio_tokens": 0,
                            "cached_tokens": 0,
                        },
                        "completion_tokens_details": {
                            "audio_tokens": 0,
                            "reasoning_tokens": 640,
                            "accepted_prediction_tokens": 0,
                            "rejected_prediction_tokens": 0,
                        },
                    },
                    "object": "chat.completion",
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": "This is the rewritten comment.",
                                "tool_calls": None,
                                "annotations": [],
                                "function_call": None,
                                "provider_specific_fields": {"refusal": None},
                            },
                            "finish_reason": "stop",
                            "provider_specific_fields": {},
                        }
                    ],
                    "created": 1785952769,
                    "moderation": None,
                    "service_tier": "default",
                    "system_fingerprint": None,
                }
            )

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.responses = FakeResponsesAPI()

    monkeypatch.setattr(openai, "OpenAI", FakeClient)
    blogitem = BlogItem.objects.create(
        oid="hello-world",
        title="Hello World",
        pub_date=timezone.now(),
    )
    blogcomment = BlogComment.objects.create(
        oid="abc123",
        blogitem=blogitem,
        parent=None,
        approved=False,
        auto_approved=False,
        comment="Bla <bla>",
        name="John Doe",
        email="",
    )

    url = reverse("api:comment_rewrite", args=[blogcomment.oid])
    response = admin_client.get(url)
    assert response.status_code == 405

    response = admin_client.post(
        url,
        json.dumps({"model": "openai-gpt-5"}),
        content_type="application/json",
    )

    assert response.status_code == 201
    data = response.json()
    assert data["rewritten"] is None
    assert data["comment"] == blogcomment.comment
    assert data["html_diff"] is None
    assert data["llm_call"]["status"] == "progress"
    assert data["llm_call"]["error"] is None

    url = reverse("api:comment_rewrite", args=[blogcomment.oid])
    response = admin_client.post(
        url,
        json.dumps({"model": "openai-gpt-5"}),
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.json()
    assert data["llm_call"]["error"] is None
    assert data["rewritten"] == "This is the rewritten comment."
    assert data["comment"] == blogcomment.comment
    assert data["html_diff"]
    assert data["llm_call"]["status"] == "success"
    assert data["llm_call"]["took_seconds"]


@pytest.mark.django_db
def test_rewrite_claude(admin_client, monkeypatch):

    class FakeMessagesAPI:
        def create(self, **kwargs):
            return Completion(
                {
                    "id": "msg_0000001",
                    "role": "assistant",
                    "type": "message",
                    "model": "claude-opus-4-8",
                    "usage": {
                        "input_tokens": 204,
                        "service_tier": "standard",
                        "inference_geo": "global",
                        "output_tokens": 33,
                        "cache_creation": {
                            "ephemeral_1h_input_tokens": 0,
                            "ephemeral_5m_input_tokens": 0,
                        },
                        "output_tokens_details": {"thinking_tokens": 0},
                        "cache_read_input_tokens": 0,
                        "cache_creation_input_tokens": 0,
                    },
                    "content": [
                        {
                            "text": "I'm trying to find the cool song.",
                            "type": "text",
                        }
                    ],
                    "stop_reason": "end_turn",
                    "stop_details": None,
                    "stop_sequence": None,
                }
            )

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.messages = FakeMessagesAPI()

    monkeypatch.setattr(anthropic, "Anthropic", FakeClient)
    blogitem = BlogItem.objects.create(
        oid="hello-world",
        title="Hello World",
        pub_date=timezone.now(),
    )
    blogcomment = BlogComment.objects.create(
        oid="abc123",
        blogitem=blogitem,
        parent=None,
        approved=False,
        auto_approved=False,
        comment="Bla <bla>",
        name="John Doe",
        email="",
    )

    url = reverse("api:comment_rewrite", args=[blogcomment.oid])
    response = admin_client.get(url)
    assert response.status_code == 405

    response = admin_client.post(
        url,
        json.dumps({"model": "claude-opus-4-8"}),
        content_type="application/json",
    )

    assert response.status_code == 201
    data = response.json()
    assert data["rewritten"] is None
    assert data["comment"] == blogcomment.comment
    assert data["html_diff"] is None
    assert data["llm_call"]["status"] == "progress"
    assert data["llm_call"]["error"] is None

    url = reverse("api:comment_rewrite", args=[blogcomment.oid])
    response = admin_client.post(
        url,
        json.dumps({"model": "claude-opus-4-8"}),
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.json()
    assert data["llm_call"]["error"] is None
    assert data["rewritten"] == "I'm trying to find the cool song."
    assert data["comment"] == blogcomment.comment
    assert data["html_diff"]
    assert data["llm_call"]["status"] == "success"
    assert data["llm_call"]["took_seconds"]


@pytest.mark.django_db
def test_rewrite_auth(client):
    url = reverse("api:comment_rewrite", args=["test-oid"])
    response = client.get(url)

    assert response.status_code == 403


@pytest.mark.django_db
def test_rewrite_bad_request(admin_client):
    url = reverse("api:comment_rewrite", args=["test-oid"])
    response = admin_client.get(url)
    assert response.status_code == 405

    response = admin_client.post(
        url,
        json.dumps({"model": "gpt-5"}),
        content_type="application/json",
    )
    assert response.status_code == 404

    blogitem = BlogItem.objects.create(
        oid="hello-world",
        title="Hello World",
        pub_date=timezone.now(),
    )
    blogcomment = BlogComment.objects.create(
        oid="abc123",
        blogitem=blogitem,
        parent=None,
        approved=False,
        auto_approved=False,
        comment="Bla <bla>",
        name="John Doe",
        email="",
    )

    url = reverse("api:comment_rewrite", args=[blogcomment.oid])
    response = admin_client.post(
        url,
        json.dumps({"model": "neverheardof"}),
        content_type="application/json",
    )
    assert response.status_code == 400
