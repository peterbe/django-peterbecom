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
    assert first["modify_date"]
    assert first["keywords"] == ["one", "two"]
    assert first["summary"] == ""
    assert first["categories"] == [{"id": category.id, "name": "Code"}]
    assert not first["has_split"]


def test_hidden_and_disallowed(admin_client):
    blogitem = BlogItem.objects.create(
        oid="hello-world",
        title="Hello World",
        pub_date=timezone.now(),
        proper_keywords=["one", "two"],
    )
    category = Category.objects.create(name="Code")
    blogitem.categories.add(category)

    url = reverse("api:blogitems_all")
    response = admin_client.get(url)
    assert response.status_code == 200
    assert response.json()["count"] == 1
    (first,) = response.json()["blogitems"]
    assert not first["hide_comments"]
    assert not first["disallow_comments"]

    blogitem.hide_comments = True
    blogitem.disallow_comments = True
    blogitem.save()
    response = admin_client.get(url)
    assert response.status_code == 200
    assert response.json()["count"] == 1
    (first,) = response.json()["blogitems"]
    assert first["hide_comments"]
    assert first["disallow_comments"]


def test_search_blogitems(admin_client):
    blogitem1 = BlogItem.objects.create(
        oid="foo-bar",
        title="Foo Bar",
        pub_date=timezone.now(),
        proper_keywords=["one", "two"],
        text="Some *text*",
        summary="Short",
    )
    category1 = Category.objects.create(name="Food")
    blogitem1.categories.add(category1)

    blogitem2 = BlogItem.objects.create(
        oid="hello-world",
        title="Hello World",
        pub_date=timezone.now() + timezone.timedelta(days=1),
        proper_keywords=["one", "two"],
        text="Some *text*",
    )
    category2 = Category.objects.create(name="Code")
    blogitem2.categories.add(category2)
    url = reverse("api:blogitems")

    response = admin_client.get(url, {"search": ""})
    assert response.status_code == 200
    found = response.json()["blogitems"]
    assert [x["id"] for x in found] == [blogitem2.id, blogitem1.id]

    response = admin_client.get(url, {"search": "has:summary"})
    assert response.status_code == 200
    found = response.json()["blogitems"]
    assert [x["id"] for x in found] == [blogitem1.id]

    response = admin_client.get(url, {"search": "no:summary"})
    assert response.status_code == 200
    found = response.json()["blogitems"]
    assert [x["id"] for x in found] == [blogitem2.id]

    response = admin_client.get(url, {"search": "is:published"})
    assert response.status_code == 200
    found = response.json()["blogitems"]
    assert [x["id"] for x in found] == [blogitem1.id]

    response = admin_client.get(url, {"search": "is:future"})
    assert response.status_code == 200
    found = response.json()["blogitems"]
    assert [x["id"] for x in found] == [blogitem2.id]

    response = admin_client.get(url, {"search": "cat: Food"})
    assert response.status_code == 200
    found = response.json()["blogitems"]
    assert [x["id"] for x in found] == [blogitem1.id]
    assert found[0]["categories"] == [{"id": category1.id, "name": "Food"}]


def test_show_all_blogitems(admin_client):
    blogitem1 = BlogItem.objects.create(
        oid="foo-bar",
        title="Foo Bar",
        pub_date=timezone.now(),
        proper_keywords=["one", "two"],
        text="Some *text*",
        summary="Short",
    )
    blogitem2 = BlogItem.objects.create(
        oid="hello-world",
        title="Hello World",
        pub_date=timezone.now() + timezone.timedelta(days=1),
        proper_keywords=["one", "two"],
        text="Some *text*",
    )
    url = reverse("api:blogitems_all")
    response = admin_client.get(url, {"minimal_fields": "true"})
    assert response.status_code == 200
    assert response.json()["count"] == 2
    found = response.json()["blogitems"]

    assert len(found) == 2
    mapped = {x["id"]: x for x in found}
    assert mapped[blogitem1.id] == {
        "oid": "foo-bar",
        "title": "Foo Bar",
        "id": blogitem1.id,
    }
    assert mapped[blogitem2.id] == {
        "oid": "hello-world",
        "title": "Hello World",
        "id": blogitem2.id,
    }


def test_search_by_split(admin_client):
    blogitem1 = BlogItem.objects.create(
        oid="hello-world",
        title="Hello World",
        text="Hello *world*\n<!--split-->Second part",
        pub_date=timezone.now(),
        proper_keywords=["one", "two"],
    )
    blogitem2 = BlogItem.objects.create(
        oid="foo-bar",
        title="Foo Bar",
        text="Fuuu bar",
        pub_date=timezone.now() - timezone.timedelta(days=1),
        proper_keywords=["three"],
    )
    url = reverse("api:blogitems")
    response = admin_client.get(url, {"order": "pub_date"})
    assert response.status_code == 200
    assert response.json()["count"] == 2
    (first, second) = response.json()["blogitems"]
    assert first["id"] == blogitem1.id
    assert second["id"] == blogitem2.id

    # Has
    response = admin_client.get(url, {"order": "pub_date", "search": "has:split"})
    assert response.status_code == 200
    assert response.json()["count"] == 1
    (first,) = response.json()["blogitems"]
    assert first["id"] == blogitem1.id

    # Has not
    response = admin_client.get(url, {"order": "pub_date", "search": "no:split"})
    assert response.status_code == 200
    assert response.json()["count"] == 1
    (first,) = response.json()["blogitems"]
    assert first["id"] == blogitem2.id


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
