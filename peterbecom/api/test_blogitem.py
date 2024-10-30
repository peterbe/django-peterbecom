import json
import pytest
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


def test_split_stands_out(admin_client):
    url = reverse("api:preview")
    response = admin_client.post(
        url,
        json.dumps(
            {
                "text": "Hello *world*\n<!--split-->\nSecond part",
                "display_format": "markdown",
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 200
    split_html = '<p class="preview-html-split">split</p>'
    before, after = response.json()["blogitem"]["html"].split(split_html)
    assert before.strip() == "<p>Hello <em>world</em></p>"
    assert after.strip() == "<p>Second part</p>"


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
        text="Hello *world*\n<!--split-->Second part",
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


def test_delete_blogitem(admin_client):
    BlogItem.objects.create(
        oid="hello-world",
        title="Hello World",
        pub_date=timezone.now(),
        proper_keywords=["one", "two"],
        display_format="markdown",
        text="Hello *world*\n<!--split-->Second part",
    )
    url = reverse("api:blogitem", args=["hello-world"])
    response = admin_client.delete(url)
    assert response.status_code == 200
    assert not BlogItem.objects.filter(oid="hello-world").exists()


@pytest.mark.django_db
def test_blogitem_auth(client):
    BlogItem.objects.create(
        oid="hello-world",
        title="Hello World",
        pub_date=timezone.now(),
        proper_keywords=["one", "two"],
        text="Hello *world*\n<!--split-->Second part",
    )
    url = reverse("api:blogitem", args=["hello-world"])
    response = client.get(url)
    assert response.status_code == 403


@pytest.mark.django_db
def test_toggle_archived_blogitem(admin_client):
    blogitem = BlogItem.objects.create(
        oid="hello-world",
        title="Hello World",
        pub_date=timezone.now(),
        proper_keywords=["one", "two"],
        display_format="markdown",
        text="Hello *world*\n<!--split-->Second part",
    )
    url = reverse("api:blogitem", args=["hello-world"])
    response = admin_client.post(
        url,
        json.dumps({"toggle_archived": True}),
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["blogitem"]["archived"]
    blogitem.refresh_from_db()
    assert blogitem.archived

    response = admin_client.post(
        url,
        json.dumps({"toggle_archived": True}),
        content_type="application/json",
    )
    assert response.status_code == 200
    assert not response.json()["blogitem"]["archived"]
    blogitem.refresh_from_db()
    assert not blogitem.archived


@pytest.mark.django_db
def test_edit_blogitem(admin_client):
    blogitem = BlogItem.objects.create(
        oid="hello-world",
        title="Hello World",
        pub_date=timezone.now(),
        proper_keywords=["one", "two"],
        display_format="markdown",
        text="Hello *world*\n<!--split-->Second part",
    )
    url = reverse("api:blogitem", args=["hello-world"])
    response = admin_client.post(
        url,
        json.dumps(
            {
                "title": "New title",
                "oid": "new-oid",
                "summary": "New summary",
                "keywords": ["three ", " four "],
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["errors"]["text"]
    assert response.json()["errors"]["pub_date"]
    assert response.json()["errors"]["categories"]

    cat1 = Category.objects.create(name="Code")
    response = admin_client.post(
        url,
        json.dumps(
            {
                "title": "New title",
                "oid": "new-oid",
                "summary": "New summary",
                "keywords": "three \n four ",  # ["three ", " four "],
                "pub_date": json_datetime(timezone.now()),
                "categories": [cat1.id],
                "text": "Hello *world*\n<!--split-->Second part",
                "display_format": "markdown",
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 200
    blogitem.refresh_from_db()
    assert blogitem.proper_keywords == ["three", "four"]
