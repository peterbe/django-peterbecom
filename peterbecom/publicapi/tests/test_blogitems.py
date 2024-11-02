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
