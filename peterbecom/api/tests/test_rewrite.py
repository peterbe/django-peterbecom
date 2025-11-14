import json

import litellm
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
def test_rewrite_happy_path(admin_client, monkeypatch):
    def mock_completion(*args, **kwargs):
        print("Hello from mock_completion")
        return Completion(
            {
                "choices": [
                    {
                        "message": {
                            "content": "This is the rewritten comment.",
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(litellm, "completion", mock_completion)
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
        json.dumps({"model": "gpt-5"}),
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
        json.dumps({"model": "gpt-5"}),
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
