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


def test_admin_required(client):
    url = reverse("api:blogitems")
    response = client.get(url)
    assert response.status_code == 403


def test_empty(admin_client):
    url = reverse("api:blogitems")
    response = admin_client.get(url)
    assert response.status_code == 200
    assert response.json()["blogitems"] == []
    assert response.json()["count"] == 0


def test_happy_path(admin_client):
    blogitem = BlogItem.objects.create(
        oid="hello-world",
        title="Hello World",
        pub_date=timezone.now(),
        proper_keywords=["one", "two"],
    )
    category = Category.objects.create(name="Code")
    blogitem.categories.add(category)

    url = reverse("api:blogitems")
    response = admin_client.get(url)
    assert response.status_code == 200
    assert response.json()["count"] == 1
    (first,) = response.json()["blogitems"]
    assert first["id"] == blogitem.id
    assert first["oid"] == "hello-world"
    assert first["title"] == "Hello World"
    assert first["archived"] is None
    assert first["pub_date"] == json_datetime(blogitem.pub_date)
    assert first["modify_date"] == json_datetime(blogitem.pub_date)
    assert first["keywords"] == ["one", "two"]
    assert first["summary"] == ""
    assert first["categories"] == [{"id": category.id, "name": "Code"}]


def test_create_blogitem(admin_client):
    url = reverse("api:blogitems")
    response = admin_client.post(
        url,
        json.dumps({}),
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["errors"]

    category = Category.objects.create(name="Code")
    response = admin_client.post(
        url,
        json.dumps(
            {
                "display_format": "markdown",
                "keywords": " one \n two ",
                "categories": [str(category.id)],
                "title": "Hello World",
                "oid": "hello-world ",
                "pub_date": json_datetime(timezone.now()),
                "text": " Some *text* ",
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 201
    assert response.json()["blogitem"]["id"]
    assert response.json()["blogitem"]["oid"] == "hello-world"

    blogitem = BlogItem.objects.get(oid="hello-world")
    assert blogitem.text == "Some *text*"
    assert blogitem.display_format == "markdown"
    assert blogitem.categories.all().count() == 1
