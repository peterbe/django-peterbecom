import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from peterbecom.plog.models import BlogComment, BlogItem, Category


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

    # Now with varying `size` parameter
    response = client.get(url, {"size": "100"})
    assert response.status_code == 400
    response = client.get(url, {"size": "0"})
    assert response.status_code == 400
    response = client.get(url, {"size": "-3"})
    assert response.status_code == 400
    response = client.get(url, {"size": "notanumber"})
    assert response.status_code == 400

    response = client.get(url, {"size": "2"})
    assert response.status_code == 200
    data = response.json()
    assert len(data["posts"]) == 2


@pytest.mark.django_db
def test_homepage_blogitems_split_html(client):
    blogitem1 = BlogItem.objects.create(
        oid="hello-world",
        title="Hello World",
        text="Hello *world*\n<!--split-->Second part",
        pub_date=timezone.now(),
        proper_keywords=["one", "two"],
    )
    assert "<p>Hello <em>world</em></p>" in blogitem1.rendered
    assert "<p>Second part</p>" in blogitem1.rendered

    blogitem2 = BlogItem.objects.create(
        oid="foo-bar",
        title="Foo Bar",
        text="Fuuu _bar_",
        pub_date=timezone.now() - timezone.timedelta(days=1),
        proper_keywords=["three"],
    )
    assert blogitem2.rendered == "<p>Fuuu <em>bar</em></p>"

    url = reverse("publicapi:homepage_blogitems")
    response = client.get(url)
    assert response.status_code == 200
    data = response.json()
    first, second = data["posts"]
    assert first["oid"] == "hello-world"
    assert second["oid"] == "foo-bar"
    assert first["split"] == len("<p>Second part</p>")
    assert second["split"] is None


@pytest.mark.django_db
def test_misc_requests(client):
    blogitem = BlogItem.objects.create(
        oid="hello-world",
        title="Hello World",
        text="Hello *world*\n<!--split-->Second part",
        pub_date=timezone.now() - datetime.timedelta(days=1),
        proper_keywords=["one", "two"],
    )
    blogitem.categories.add(Category.objects.create(name="Category"))

    blogitem2 = BlogItem.objects.create(
        oid="foo-bar",
        title="Foo Bar",
        text="Foo *bar*",
        pub_date=timezone.now(),
        proper_keywords=["one", "two"],
    )
    blogitem2.categories.add(Category.objects.create(name="Foodware"))

    BlogComment.objects.create(
        blogitem=blogitem, oid="123", name="Peter", comment="Hi", approved=True
    )
    BlogComment.objects.create(
        blogitem=blogitem2, oid="xyz", name="Stranger", comment="Uh?", approved=False
    )

    url = reverse("publicapi:homepage_blogitems")
    response = client.get(url)
    assert response.status_code == 200
    posts = response.json()["posts"]
    # because they're sorted by pub_date, the order is predictable
    first, second = posts
    assert first["comments"] == 0
    assert second["comments"] == 1

    url = reverse("publicapi:homepage_blogitems")
    response = client.get(url, {"oc": "one"})
    assert response.status_code == 400

    response = client.get(url, {"oc": "cateGory"})
    assert response.status_code == 301

    response = client.get(url, {"oc": "Category"})
    assert response.status_code == 200
    posts = response.json()["posts"]
    oids = [x["oid"] for x in posts]
    assert "hello-world" in oids
    assert "foo-bar" not in oids

    # HEAD is always empty
    response = client.head(url)
    assert response.status_code == 200
    payload = response.content.decode("utf-8")
    assert payload == ""
