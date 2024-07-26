import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from peterbecom.plog.models import BlogItem, Category


@pytest.mark.django_db
def test_blogitem_bad_request(client):
    url = reverse("publicapi:blogitem", args=["never.heard.of"])
    response = client.get(url)
    assert response.status_code == 404

    blog_item = BlogItem.objects.create(
        oid="o-i.d",
        title="Title",
        text="*Text*",
        text_rendered=BlogItem.render("*Text*", "markdown", ""),
        display_format="markdown",
        summary="Summary",
        pub_date=timezone.now() + datetime.timedelta(days=100),
    )
    url = reverse("publicapi:blogitem", args=["O-i.D"])
    response = client.get(url)
    assert response.status_code == 404
    blog_item.pub_date = timezone.now()
    blog_item.archived = timezone.now()
    blog_item.save()
    assert response.status_code == 404

    blog_item.archived = None
    blog_item.save()
    response = client.get(url, {"page": "xxx"})
    assert response.status_code == 400
    response = client.get(url, {"page": "0"})
    assert response.status_code == 400
    response = client.get(url, {"page": "2"})
    assert response.status_code == 404
    # sanity check
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_blogitem_basic(client):
    blog_item = BlogItem.objects.create(
        oid="oid",
        title="Title",
        text="*Text*",
        text_rendered=BlogItem.render("*Text*", "markdown", ""),
        display_format="markdown",
        summary="Summary",
        pub_date=timezone.now(),
    )
    blog_item.categories.add(Category.objects.create(name="Category"))
    url = reverse("publicapi:blogitem", args=["oid"])
    response = client.get(url)
    assert response.status_code == 200
    data = response.json()
    assert data["post"]["title"] == "Title"
    assert data["post"]["body"] == "<p><em>Text</em></p>"
    assert data["post"]["categories"] == ["Category"]
    assert data["post"]["next_post"] is None
    assert data["post"]["previous_post"] is None
    assert data["post"]["oid"] == "oid"
    assert data["post"]["open_graph_image"] is None
    assert data["post"]["pub_date"].startswith(blog_item.pub_date.strftime("%Y-%m-%d"))
    assert data["post"]["url"] is None
    assert data["post"]["summary"] == "Summary"
    assert data["post"]["related_by_keyword"] == []
    assert data["post"]["related_by_category"] == []
