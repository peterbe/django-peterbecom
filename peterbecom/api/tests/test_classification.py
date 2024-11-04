import json

from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse
from django.utils import timezone

from peterbecom.plog.models import (
    BlogComment,
    BlogCommentClassification,
    BlogItem,
    Category,
)


def json_datetime(obj):
    return DjangoJSONEncoder().default(obj)


def test_admin_required(client):
    url = reverse("api:comment_classify", args=("abc123",))
    response = client.get(url)
    assert response.status_code == 403
    response = client.delete(url)
    assert response.status_code == 403
    response = client.post(url)
    assert response.status_code == 403


def test_happy_path(admin_client):
    blogitem = BlogItem.objects.create(
        oid="hello-world",
        title="Hello World",
        pub_date=timezone.now(),
        proper_keywords=["one", "two"],
    )
    category = Category.objects.create(name="Code")
    blogitem.categories.add(category)
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
    url = reverse("api:comment_classify", args=("notheardof",))
    response = admin_client.post(url)
    assert response.status_code == 404

    url = reverse("api:comment_classify", args=(blogcomment.oid,))
    response = admin_client.get(url)
    assert response.status_code == 200
    assert response.json() == {"classification": None, "choices": []}
    response = admin_client.post(url)
    assert response.status_code == 400

    response = admin_client.post(
        url,
        json.dumps(
            {
                "text": blogcomment.comment,
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 400

    response = admin_client.post(
        url,
        json.dumps({"text": blogcomment.comment, "classification": "spam"}),
        content_type="application/json",
    )
    assert response.status_code == 201
    assert response.json()["ok"] is True
    assert BlogCommentClassification.objects.all().count() == 1

    response = admin_client.post(
        url,
        json.dumps({"text": blogcomment.comment, "classification": "Spam"}),
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert BlogCommentClassification.objects.all().count() == 1

    response = admin_client.get(url)
    assert response.status_code == 200
    data = response.json()
    assert data["choices"] == [
        {"count": 1, "value": "spam"},
    ]
    assert data["classification"]["id"]
    assert data["classification"]["text"]
    assert data["classification"]["add_date"]
    assert data["classification"]["modify_date"]
    assert data["classification"]["classification"] == "spam"

    (classification,) = BlogCommentClassification.objects.all()

    response = admin_client.delete(url)
    assert response.status_code == 400

    response = admin_client.delete(f"{url}?id={classification.id}")
    assert response.status_code == 200
    assert BlogCommentClassification.objects.all().count() == 0
