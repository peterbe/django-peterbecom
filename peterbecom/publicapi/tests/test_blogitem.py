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
def test_blogitem_archived(client):
    blogitem = BlogItem.objects.create(
        oid="oid",
        title="Title",
        text="*Text*",
        text_rendered=BlogItem.render("*Text*", "markdown", ""),
        display_format="markdown",
        summary="Summary",
        pub_date=timezone.now(),
        archived=timezone.now(),
    )
    blogitem.categories.add(Category.objects.create(name="Category"))
    url = reverse("publicapi:blogitem", args=["oid"])
    response = client.get(url)
    assert response.status_code == 404


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
def test_blogcomment_happy_path(client):
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

    BlogComment.objects.create(
        blogitem=blogitem,
        oid="c-oid",
        name="Commenter",
        email="test@example.com",
        comment="Foo\nBar",
        approved=True,
    )
    url = reverse("publicapi:blogcomment", args=["oid", "c-oid"])
    response = client.get(url)
    assert response.status_code == 200
    data = response.json()

    assert data["page"] == 1

    assert data["parent"] is None

    assert data["post"]["disallow_comments"] is False
    assert data["post"]["oid"] == "oid"
    assert data["post"]["open_graph_image"] is None
    assert data["post"]["summary"] == blogitem.summary
    assert data["post"]["title"] == blogitem.title

    assert data["comment"]["name"] == "Commenter"
    assert data["comment"]["approved"] is True
    assert "email" not in data["comment"]
    assert data["comment"]["add_date"]
    assert data["comment"]["oid"] == "c-oid"
    assert data["comment"]["id"]
    assert data["comment"]["comment"] == "Foo<br>Bar"


@pytest.mark.django_db
def test_blogcomment_not_found(client):
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

    BlogComment.objects.create(
        blogitem=blogitem,
        oid="c-oid",
        name="Commenter",
        email="test@example.com",
        comment="Foo\nBar",
        approved=True,
    )
    url = reverse("publicapi:blogcomment", args=["xxx", "c-oid"])
    response = client.get(url)
    assert response.status_code == 404
    url = reverse("publicapi:blogcomment", args=["oid", "xxx"])
    response = client.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_blogcomment_page(client, settings):
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

    bulk = []
    last_comment_oid = None
    for i in range(settings.MAX_RECENT_COMMENTS + 1):
        bulk.append(
            BlogComment(
                blogitem=blogitem,
                parent=None,
                oid=f"c-oid-{i + 1}",
                name=f"Commenter {i + 1}",
                email="test@example.com",
                comment="Foo\nBar",
                approved=True,
                add_date=timezone.now()
                - datetime.timedelta(hours=1)
                - datetime.timedelta(minutes=i + 1),
            )
        )
        last_comment_oid = f"c-oid-{i + 1}"
    BlogComment.objects.bulk_create(bulk)
    url = reverse(
        "publicapi:blogcomment",
        args=["oid", f"c-oid-{settings.MAX_RECENT_COMMENTS}"],
    )
    response = client.get(url)
    assert response.status_code == 200
    assert response.json()["page"] == 1
    url = reverse(
        "publicapi:blogcomment",
        args=["oid", f"c-oid-{settings.MAX_RECENT_COMMENTS + 1}"],
    )
    response = client.get(url)
    assert response.status_code == 200
    assert response.json()["page"] == 2

    last_comment = BlogComment.objects.get(oid=last_comment_oid)
    BlogComment.objects.create(
        blogitem=blogitem,
        parent=last_comment,
        oid=last_comment_oid + "-child",
        name=f"Commenter {i + 1} Child",
        email="test@example.com",
        comment="Foo\nBar",
        approved=True,
        add_date=last_comment.add_date + datetime.timedelta(minutes=i + 1),
    )
    url = reverse(
        "publicapi:blogcomment",
        args=["oid", f"{last_comment_oid}-child"],
    )
    response = client.get(url)
    assert response.status_code == 200
    assert response.json()["page"] == 2


@pytest.mark.django_db
def test_blogcomment_parent_and_replies(client):
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

    root_comment = BlogComment.objects.create(
        blogitem=blogitem,
        parent=None,
        oid="c-oid-root",
        name="Root Commenter",
        email="root@example.com",
        comment="Root Comment",
        approved=True,
        add_date=timezone.now(),
    )
    reply_comment = BlogComment.objects.create(
        blogitem=blogitem,
        parent=root_comment,
        oid="c-oid-reply",
        name="Reply Commenter",
        email="reply@example.com",
        comment="Reply Comment",
        approved=True,
        add_date=timezone.now(),
    )
    reply_reply_comment = BlogComment.objects.create(
        blogitem=blogitem,
        parent=reply_comment,
        oid="c-oid-reply-reply",
        name="Reply Reply Commenter",
        email="reply-reply@example.com",
        comment="Reply Reply Comment",
        approved=True,
        add_date=timezone.now(),
    )

    #
    # Grand-child comment
    #
    url = reverse(
        "publicapi:blogcomment",
        args=["oid", "c-oid-reply-reply"],
    )
    response = client.get(url)
    assert response.status_code == 200
    data = response.json()

    assert data["page"] == 1
    assert data["comment"]["add_date"]
    assert data["comment"]["approved"]
    assert data["comment"]["comment"] == "Reply Reply Comment"
    assert data["comment"]["depth"] == 0
    assert data["comment"]["id"] == reply_reply_comment.id
    assert data["post"]["title"] == blogitem.title
    assert data["parent"]["oid"] == "c-oid-reply"
    assert data["parent"]["add_date"]
    assert data["parent"]["approved"]
    assert data["parent"]["blogitem_id"] == blogitem.id
    assert data["parent"]["depth"] == 0
    assert data["parent"]["id"] == reply_comment.id
    assert data["parent"]["name"] == reply_comment.name
    assert "email" not in data["parent"]
    assert data["parent"]["parent_id"] == root_comment.id

    #
    # Child comment
    #
    url = reverse(
        "publicapi:blogcomment",
        args=["oid", "c-oid-reply"],
    )
    response = client.get(url)
    assert response.status_code == 200
    data = response.json()

    assert data["page"] == 1
    assert data["post"]["title"] == blogitem.title
    assert data["comment"]["add_date"]
    assert data["comment"]["approved"]
    assert data["comment"]["comment"] == "Reply Comment"
    assert data["comment"]["depth"] == 0
    assert data["comment"]["id"] == reply_comment.id
    assert data["parent"]["oid"] == root_comment.oid
    assert data["parent"]["add_date"]
    assert data["parent"]["approved"]
    assert data["parent"]["blogitem_id"] == blogitem.id
    assert data["parent"]["depth"] == 0
    assert data["parent"]["id"] == root_comment.id
    assert data["parent"]["oid"] == root_comment.oid
    assert data["parent"]["parent_id"] is None

    assert data["replies"]["next_page"] is None
    assert data["replies"]["previous_page"] is None
    assert data["replies"]["total_pages"] == 1
    assert not data["replies"]["truncated"]
    assert len(data["replies"]["tree"]) == 1
    assert data["replies"]["tree"][0]["add_date"]
    assert data["replies"]["tree"][0]["approved"]
    assert data["replies"]["tree"][0]["comment"] == "Reply Reply Comment"
    assert data["replies"]["tree"][0]["depth"] == 0
    assert data["replies"]["tree"][0]["id"] == reply_reply_comment.id
    assert data["replies"]["tree"][0]["name"] == reply_reply_comment.name
    assert "email" not in data["replies"]["tree"][0]
    assert data["replies"]["tree"][0]["oid"] == reply_reply_comment.oid

    #
    # Root comment
    #
    url = reverse(
        "publicapi:blogcomment",
        args=["oid", "c-oid-root"],
    )
    response = client.get(url)
    assert response.status_code == 200
    data = response.json()

    assert data["page"] == 1
    assert data["parent"] is None
    assert data["post"]["title"] == blogitem.title
    assert data["comment"]["add_date"]
    assert data["comment"]["approved"]
    assert data["comment"]["comment"] == "Root Comment"
    assert data["comment"]["depth"] == 0
    assert data["comment"]["id"] == root_comment.id

    assert data["replies"]["next_page"] is None
    assert data["replies"]["previous_page"] is None
    assert data["replies"]["total_pages"] == 1
    assert not data["replies"]["truncated"]
    assert len(data["replies"]["tree"]) == 1
    assert data["replies"]["tree"][0]["add_date"]
    assert data["replies"]["tree"][0]["approved"]
    assert data["replies"]["tree"][0]["comment"] == "Reply Comment"
    assert data["replies"]["tree"][0]["depth"] == 0
    assert data["replies"]["tree"][0]["id"] == reply_comment.id
    assert data["replies"]["tree"][0]["name"] == reply_comment.name
    assert "email" not in data["replies"]["tree"][0]
    assert data["replies"]["tree"][0]["oid"] == reply_comment.oid

    inner_replies = data["replies"]["tree"][0]["replies"]

    assert inner_replies[0]["add_date"]
    assert inner_replies[0]["approved"]
    assert inner_replies[0]["depth"] == 1
    assert inner_replies[0]["id"] == reply_reply_comment.id
    assert inner_replies[0]["name"] == reply_reply_comment.name
    assert "email" not in inner_replies[0]["name"]
    assert inner_replies[0]["oid"] == reply_reply_comment.oid

    url = reverse("publicapi:blogitem", args=[blogitem.oid])
    response = client.get(url)
    assert response.status_code == 200
    data = response.json()

    assert data["comments"]["count"] == 3
    assert data["comments"]["next_page"] is None
    assert data["comments"]["previous_page"] is None
    assert data["comments"]["total_pages"] == 1
    tree = data["comments"]["tree"]
    assert len(tree) == 1
    assert tree[0]["id"] == root_comment.id
    assert tree[0]["depth"] == 0
    assert tree[0]["approved"]
    assert tree[0]["add_date"]
    assert tree[0]["name"] == root_comment.name
    assert tree[0]["oid"] == root_comment.oid
    assert tree[0]["id"] == root_comment.id
    replies = tree[0]["replies"]

    assert len(replies) == 1
    assert replies[0]["add_date"]
    assert replies[0]["approved"]
    assert replies[0]["comment"] == reply_comment.comment
    assert replies[0]["depth"] == 1
    assert replies[0]["oid"] == reply_comment.oid
    assert replies[0]["id"] == reply_comment.id
    reply_replies = replies[0]["replies"]
    assert len(reply_replies) == 1
    assert reply_replies[0]["add_date"]
    assert reply_replies[0]["approved"]
    assert reply_replies[0]["comment"] == reply_reply_comment.comment
    assert reply_replies[0]["depth"] == 2
    assert reply_replies[0]["id"] == reply_reply_comment.id
    assert reply_replies[0]["oid"] == reply_reply_comment.oid
    assert reply_replies[0]["name"] == reply_reply_comment.name
    assert "email" not in reply_replies[0]["name"]
