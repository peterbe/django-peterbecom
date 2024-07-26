import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from peterbecom.plog.models import BlogItem, Category


@pytest.mark.django_db
def test_homepage_blogitems_empty(client):
    url = reverse("publicapi:homepage_blogitems")
    response = client.get(url)
    assert response.status_code == 200
    data = response.json()
    assert data["posts"] == []
    assert not data["next_page"]
    assert not data["previous_page"]


@pytest.mark.django_db
def test_homepage_blogitems_bad_request(client):
    url = reverse("publicapi:homepage_blogitems")
    response = client.get(url, {"page": "0"})
    assert response.status_code == 400
    response = client.get(url, {"page": "notanumber"})
    assert response.status_code == 400
    response = client.get(url, {"oc": "neverheardof"})
    assert response.status_code == 400
    response = client.get(url, {"page": "2"})
    assert response.status_code == 404


@pytest.mark.django_db
def test_homepage_blogitems_happy_path(client, settings):
    settings.HOMEPAGE_BATCH_SIZE = 3
    bulk = []
    for i in range(7):
        text = f"**Text** `{i +1}`"
        bulk.append(
            BlogItem(
                oid=f"oid-{i+1}",
                title=f"Title {i+1}",
                text=text,
                text_rendered=BlogItem.render(text, "markdown", ""),
                display_format="markdown",
                summary="",
                pub_date=timezone.now() - datetime.timedelta(seconds=i),
            )
        )
    BlogItem.objects.bulk_create(bulk)
    BlogItem.objects.get(oid="oid-1").categories.add(
        Category.objects.create(name="Category 1")
    )
    url = reverse("publicapi:homepage_blogitems")
    response = client.get(url)
    assert response.status_code == 200
    data = response.json()
    assert data["next_page"] == 2
    assert data["previous_page"] is None

    assert len(data["posts"]) == 3
    first = data["posts"][0]
    assert first["categories"] == ["Category 1"]
    assert first["comments"] == 0
    assert first["oid"] == "oid-1"
    assert first["title"] == "Title 1"
    assert first["html"] == "<p><strong>Text</strong> <code>1</code></p>"

    response = client.get(url, {"page": "2"})
    assert response.status_code == 200
    data = response.json()
    assert data["next_page"] == 3
    assert data["previous_page"] == 1

    response = client.get(url, {"page": "3"})
    assert response.status_code == 200
    data = response.json()
    assert data["next_page"] is None
    assert data["previous_page"] == 2
