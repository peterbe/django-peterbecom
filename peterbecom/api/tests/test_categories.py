import json

from django.urls import reverse
from django.utils import timezone

from peterbecom.plog.models import (
    BlogItem,
    Category,
)


def test_admin_required(client):
    url = reverse("api:categories")
    response = client.get(url)
    assert response.status_code == 403


def test_empty(admin_client):
    url = reverse("api:categories")
    response = admin_client.get(url)
    assert response.status_code == 200
    assert response.json() == {"categories": []}


def test_happy_path(admin_client):
    Category.objects.create(name="Foodware")
    blogitem = BlogItem.objects.create(
        oid="hello-world",
        title="Hello World",
        pub_date=timezone.now(),
        proper_keywords=["one", "two"],
    )
    blogitem.categories.add(Category.objects.create(name="Hatware"))

    url = reverse("api:categories")
    response = admin_client.get(url)
    assert response.status_code == 200

    # they're sorted by use
    first, second = response.json()["categories"]
    assert first["count"] == 1
    assert first["id"]
    assert first["name"] == "Hatware"
    assert second["count"] == 0
    assert second["id"]
    assert second["name"] == "Foodware"


def test_add_and_edit_category(admin_client):
    url = reverse("api:categories")
    response = admin_client.post(
        url,
        json.dumps({"name": "Newnewss", "category": ""}),
        content_type="application/json",
    )
    assert response.status_code == 201
    response = admin_client.get(url)
    assert response.status_code == 200
    (first,) = response.json()["categories"]
    assert first["name"] == "Newnewss"

    response = admin_client.post(
        url,
        json.dumps({"name": "Newnewss2", "category": str(first["id"])}),
        content_type="application/json",
    )
    response = admin_client.get(url)
    assert response.status_code == 200
    (first,) = response.json()["categories"]
    assert first["name"] == "Newnewss2"

    response = admin_client.delete(f"{url}?id=999")
    assert response.status_code == 404
    response = admin_client.delete(f"{url}?id={first['id']}")
    assert response.status_code == 200

    response = admin_client.get(url)
    assert response.status_code == 200
    assert not response.json()["categories"]
