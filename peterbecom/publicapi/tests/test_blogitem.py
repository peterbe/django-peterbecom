import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from peterbecom.plog.models import BlogComment, BlogItem, Category


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
    blogitem = BlogItem.objects.create(
        oid="oid",
        title="Title",
        text="*Text*",
        text_rendered=BlogItem.render("*Text*", "markdown", ""),
        display_format="markdown",
        summary="Summary",
        pub_date=timezone.now(),
    )
    blogitem.categories.add(Category.objects.create(name="Category"))
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
    assert data["post"]["pub_date"].startswith(blogitem.pub_date.strftime("%Y-%m-%d"))
    assert data["post"]["url"] is None
    assert data["post"]["summary"] == "Summary"
    assert data["post"]["related_by_keyword"] == []
    assert data["post"]["related_by_category"] == []


@pytest.mark.django_db
def test_blogitem_paginated_comments(client):
    blogitem = BlogItem.objects.create(
        oid="oid",
        title="Title",
        text="*Text*",
        display_format="markdown",
        summary="Summary",
        pub_date=timezone.now(),
    )
    blogitem.categories.add(Category.objects.create(name="Category"))
    bulk = []
    for i in range(100):
        bulk.append(
            BlogComment(
                blogitem=blogitem,
                oid=f"oid{i}",
                name="Name",
                email="name@example.com",
                comment=f"Comment number {i + 1}",
                approved=True,
            )
        )
    BlogComment.objects.bulk_create(bulk)

    url = reverse("publicapi:blogitem", args=["oid"])
    response = client.get(url, {"page": "99"})
    assert response.status_code == 404

    url = reverse("publicapi:blogitem", args=["oid"])
    response = client.get(url)
    comments = response.json()["comments"]
    assert comments["count"] == 100
    assert comments["next_page"] == 2
    assert comments["previous_page"] is None
    assert comments["total_pages"] > 1
    first_page_1 = comments["tree"][0]

    response = client.get(url, {"page": "2"})
    comments = response.json()["comments"]
    assert comments["count"] == 100
    assert comments["previous_page"] == 1
    assert comments["total_pages"] > 1
    second_page_1 = comments["tree"][0]
    assert first_page_1["id"] != second_page_1["id"]

    # Delete a random comment
    for comment in BlogComment.objects.all().order_by("?")[:1]:
        comment.delete()

    response = client.get(url, {"page": "2"})
    comments = response.json()["comments"]
    assert comments["count"] == 100


@pytest.mark.django_db
def test_blogitems_by_category(client):
    blogitem0 = BlogItem.objects.create(
        oid="oid-0",
        title="Lonely",
        text="*Text*",
        pub_date=timezone.now() - datetime.timedelta(days=3),
        proper_keywords=["un", "heard", "of"],
    )
    blogitem0.categories.add(Category.objects.create(name="Lone"))

    blogitem1 = BlogItem.objects.create(
        oid="oid",
        title="Title",
        text="*Text*",
        pub_date=timezone.now() - datetime.timedelta(days=2),
        proper_keywords=["one", "two"],
    )
    cat1 = Category.objects.create(name="Category")
    blogitem1.categories.add(cat1)

    blogitem2 = BlogItem.objects.create(
        oid="oid2",
        title="Title Two",
        text="*Text*",
        pub_date=timezone.now() - datetime.timedelta(days=1),
        proper_keywords=["two", "three"],
    )
    blogitem2.categories.add(cat1)
    cat2 = Category.objects.create(name="Foodware")
    blogitem2.categories.add(cat2)

    url = reverse("publicapi:blogitem", args=["oid"])
    response = client.get(url)
    assert response.status_code == 200
    previous_post = response.json()["post"]["previous_post"]
    assert previous_post["oid"] == "oid-0"
    assert previous_post["title"] == "Lonely"
    assert previous_post["categories"] == ["Lone"]
    next_post = response.json()["post"]["next_post"]
    assert next_post["oid"] == "oid2"
    assert next_post["title"] == "Title Two"
    assert next_post["categories"] == [cat1.name, cat2.name]

    blogitem02 = BlogItem.objects.create(
        oid="oid-02",
        title="Lonely Second",
        text="*Text*",
        pub_date=timezone.now() - datetime.timedelta(days=0.5),
        proper_keywords=["differ", "ent"],
    )
    blogitem02.categories.add(Category.objects.get(name="Lone"))
    url = reverse("publicapi:blogitem", args=["oid-02"])
    response = client.get(url)
    assert response.status_code == 200
    related_by_category = response.json()["post"]["related_by_category"]
    assert related_by_category[0]["oid"] == "oid-0"
    assert related_by_category[0]["categories"] == ["Lone"]

    BlogItem.objects.create(
        oid="oid-03",
        title="Keyword related",
        text="*Text*",
        pub_date=timezone.now() - datetime.timedelta(days=0.1),
        proper_keywords=["have", "heard"],
    )
    url = reverse("publicapi:blogitem", args=["oid-03"])
    response = client.get(url)
    assert response.status_code == 200
    related_by_keyword = response.json()["post"]["related_by_keyword"]
    assert related_by_keyword[0]["oid"] == "oid-0"
    assert related_by_keyword[0]["categories"] == ["Lone"]


@pytest.mark.django_db
def test_blogitem_with_comment_oid(client):
    blogitem = BlogItem.objects.create(
        oid="oid",
        title="Title",
        text="*Text*",
        text_rendered=BlogItem.render("*Text*", "markdown", ""),
        display_format="markdown",
        summary="Summary",
        pub_date=timezone.now(),
    )
    blogitem.categories.add(Category.objects.create(name="Category"))
    url = reverse("publicapi:blogitem", args=["oid"])
    response = client.get(url, {"comment": "doesnotexist"})
    assert response.status_code == 404

    blog_comment = BlogComment.objects.create(
        blogitem=blogitem,
        oid="commentoid",
        name="Name",
        email="name@example.com",
        comment="Bla bla",
        approved=True,
    )
    response = client.get(url, {"comment": blog_comment.oid})
    assert response.status_code == 200

    blog_comment.oid = "otheroid"
    blog_comment.approved = False
    blog_comment.add_date = timezone.now() - datetime.timedelta(minutes=1)
    blog_comment.save()
    response = client.get(url, {"comment": blog_comment.oid})
    assert response.status_code == 200

    blog_comment.oid = "thirdoid"
    blog_comment.add_date = timezone.now() - datetime.timedelta(hours=1)
    blog_comment.save()
    response = client.get(url, {"comment": blog_comment.oid})
    assert response.status_code == 404
