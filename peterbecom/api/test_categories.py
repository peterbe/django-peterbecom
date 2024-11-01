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
