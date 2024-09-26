import json

from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse
from django.utils import timezone

from peterbecom.plog.models import (
    BlogItem,
    Category,
)


def json_datetime(obj):
    return DjangoJSONEncoder().default(obj)


def test_preview_blogitem_happy_path(admin_client):
    url = reverse("api:preview")
    response = admin_client.post(
        url,
        json.dumps(
            {
                "text": "Hello *world*",
                "display_format": "markdown",
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 200


def test_preview_blogitem_validation_error(admin_client):
    url = reverse("api:preview")
    response = admin_client.post(
        url,
        json.dumps(
            {
                # "text": "Hello *world*",
                "display_format": "markdown",
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["blogitem"]["errors"]["text"]


def test_preview_blogitem_unauth(client):
    url = reverse("api:preview")
    response = client.post(
        url,
        json.dumps(
            {
                "text": "Hello *world*",
                "display_format": "markdown",
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 403


def test_preview_blogitem_require_post(admin_client):
    url = reverse("api:preview")
    response = admin_client.get(url)
    assert response.status_code == 405


def test_admin_required(client):
    url = reverse("api:blogitem", args=["hello-world"])
    response = client.get(url)
    assert response.status_code == 403


def test_happy_path_blogitem(admin_client):
    blogitem = BlogItem.objects.create(
        oid="hello-world",
        title="Hello World",
        pub_date=timezone.now(),
        proper_keywords=["one", "two"],
        display_format="markdown",
        text="Hello *world*",
    )
    category = Category.objects.create(name="Code")
    blogitem.categories.add(category)

    url = reverse("api:blogitem", args=["hello-world"])
    response = admin_client.get(url)
    assert response.status_code == 200

    first = response.json()["blogitem"]
    assert first["_absolute_url"] == "/plog/hello-world"
    assert first["_published"] is True
    assert first["archived"] is None
    assert first["categories"] == [{"id": category.id, "name": "Code"}]
    assert first["codesyntax"] == ""
    assert first["display_format"] == "markdown"
    assert first["disallow_comments"] is False
    assert first["hide_comments"] is False
    assert first["keywords"] == ["one", "two"]
    assert first["modify_date"] == json_datetime(blogitem.modify_date)
    assert first["pub_date"] == json_datetime(blogitem.pub_date)
    assert first["url"] is None
    assert first["id"] == blogitem.id
    assert first["summary"] == ""
