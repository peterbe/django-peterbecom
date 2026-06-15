import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from peterbecom.plog.models import BlogComment, BlogItem, Category


@pytest.mark.django_db
def test_blogitems_empty(client):
    url = reverse("publicapi:blogitems")
    response = client.get(url)
    assert response.status_code == 200
    assert not response.json()["groups"]


@pytest.mark.django_db
def test_happy_path(client):
    pub_date = timezone.now() - datetime.timedelta(days=1)
    blogitem = BlogItem.objects.create(
        oid="o-i.d",
        title="Title",
        text="*Text*",
        text_rendered=BlogItem.render("*Text*", "markdown", ""),
        display_format="markdown",
        summary="Summary",
        pub_date=pub_date,
    )
    cat1 = Category.objects.create(name="Foodware")
    blogitem.categories.add(cat1)

    BlogComment.objects.create(
        blogitem=blogitem, oid="123", name="Peter", comment="Hi", approved=True
    )
    BlogComment.objects.create(
        blogitem=blogitem, oid="xyz", name="Stranger", comment="Uh?", approved=False
    )

    url = reverse("publicapi:blogitems")
    response = client.get(url)
    assert response.status_code == 200
    assert response.json()["groups"]

    (first_group,) = response.json()["groups"]
    assert first_group["date"] == pub_date.strftime("%Y.%m")
    (first_post,) = first_group["posts"]
    assert first_post["categories"] == ["Foodware"]
    assert first_post["comments"] == 1
    assert first_post["id"]
    assert first_post["oid"] == blogitem.oid
    assert first_post["title"] == blogitem.title
    assert first_post["pub_date"]


@pytest.mark.django_db
def test_is_photo_filter(client):
    BlogItem.objects.create(
        oid="photo1",
        title="Photo 1",
        text="Photo 1",
        pub_date=timezone.now(),
        is_photo=True,
    )
    BlogItem.objects.create(
        oid="notphoto1",
        title="Not Photo 1",
        text="Not Photo 1",
        pub_date=timezone.now(),
        is_photo=False,
    )

    url = reverse("publicapi:blogitems")
    response = client.get(url)
    assert response.status_code == 200
    posts = response.json()["groups"][0]["posts"]
    assert len(posts) == 2
    oids = set([x["oid"] for x in posts])
    assert oids == {"photo1", "notphoto1"}

    response = client.get(url, {"is_photo": "false"})
    assert response.status_code == 200
    posts = response.json()["groups"][0]["posts"]
    assert len(posts) == 1
    assert posts[0]["oid"] == "notphoto1"

    response = client.get(url, {"is_photo": "true"})
    assert response.status_code == 200
    posts = response.json()["groups"][0]["posts"]
    assert len(posts) == 1
    assert posts[0]["oid"] == "photo1"
