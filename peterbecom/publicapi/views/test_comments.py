import pytest
from django.urls import reverse
from django.utils import timezone

from peterbecom.plog.models import BlogComment, BlogItem


@pytest.mark.django_db
def test_submit_comment(client):
    url = reverse("publicapi:submit_comment")
    response = client.get(url)
    assert response.status_code == 405

    blogitem = BlogItem.objects.create(
        oid="oid",
        title="Title",
        text="*Text*",
        text_rendered=BlogItem.render("*Text*", "markdown", ""),
        display_format="markdown",
        summary="Summary",
        pub_date=timezone.now(),
    )

    response = client.post(
        url,
        {
            "oid": blogitem.oid,
        },
    )
    assert response.status_code == 400
    error = response.json()

    assert error["error"]["comment"]

    response = client.post(url, {"oid": blogitem.oid, "comment": "Comment text "})
    assert response.status_code == 200

    assert response.json()["comment"] == "Comment text"
    assert BlogComment.objects.filter(blogitem=blogitem).count() == 1


@pytest.mark.django_db
def test_submit_comment_x_forward_for(client):
    url = reverse("publicapi:submit_comment")
    blogitem = BlogItem.objects.create(
        oid="oid",
        title="Title",
        text="*Text*",
        text_rendered=BlogItem.render("*Text*", "markdown", ""),
        display_format="markdown",
        summary="Summary",
        pub_date=timezone.now(),
    )

    response = client.post(
        url,
        {"oid": blogitem.oid, "comment": "Comment text "},
        headers={
            "x-forwarded-for": "2601:201:8a7e:38e0:79f6:4326:ff50:23b3, 68.70.197.65"
        },
    )
    assert response.status_code == 200
    data = response.json()

    blog_comment = BlogComment.objects.get(blogitem=blogitem, oid=data["oid"])
    assert blog_comment.ip_address == "2601:201:8a7e:38e0:79f6:4326:ff50:23b3"


@pytest.mark.django_db
def test_submit_with_name_and_email(client):
    url = reverse("publicapi:submit_comment")
    blogitem = BlogItem.objects.create(
        oid="oid",
        title="Title",
        text="*Text*",
        text_rendered=BlogItem.render("*Text*", "markdown", ""),
        display_format="markdown",
        summary="Summary",
        pub_date=timezone.now(),
    )

    response = client.post(
        url,
        {
            "oid": blogitem.oid,
            "comment": "Comment text ",
            "name": "John Doe",
            "email": "not@exa @@mple.com ",
        },
    )
    assert response.status_code == 400
    error = response.json()
    assert error["error"]["email"]

    response = client.post(
        url,
        {
            "oid": blogitem.oid,
            "comment": "Comment text ",
            "name": "\tJohn Doe",
            "email": "not@example.com ",
        },
    )
    assert response.status_code == 200
    data = response.json()

    blog_comment = BlogComment.objects.get(blogitem=blogitem, oid=data["oid"])
    assert blog_comment.email == "not@example.com"
    assert blog_comment.name == "John Doe"


@pytest.mark.django_db
def test_submit_comment_reply(client):
    url = reverse("publicapi:submit_comment")
    response = client.get(url)
    assert response.status_code == 405

    blogitem = BlogItem.objects.create(
        oid="oid",
        title="Title",
        text="*Text*",
        text_rendered=BlogItem.render("*Text*", "markdown", ""),
        display_format="markdown",
        summary="Summary",
        pub_date=timezone.now(),
    )
    parent = BlogComment.objects.create(
        blogitem=blogitem,
        comment="Bla bla",
        approved=True,
        oid="abc123",
    )

    response = client.post(
        url,
        {
            "oid": blogitem.oid,
            "comment": "   ",
            "parent": "XXX",
        },
    )
    assert response.status_code == 400
    error = response.json()
    assert error["error"]["parent"]
    assert error["error"]["comment"]

    response = client.post(
        url,
        {"oid": blogitem.oid, "parent": parent.oid, "comment": "Comment text "},
    )

    assert response.status_code == 200

    assert response.json()["comment"] == "Comment text"
    assert BlogComment.objects.filter(blogitem=blogitem).count() == 2
    assert BlogComment.objects.filter(blogitem=blogitem, parent=parent).count() == 1


@pytest.mark.django_db
def test_submit_comment_edit(client):
    url = reverse("publicapi:submit_comment")
    blogitem = BlogItem.objects.create(
        oid="oid",
        title="Title",
        text="*Text*",
        text_rendered=BlogItem.render("*Text*", "markdown", ""),
        display_format="markdown",
        summary="Summary",
        pub_date=timezone.now(),
    )

    response = client.post(
        url,
        {
            "oid": blogitem.oid,
            "comment": "Foo",
        },
    )
    assert response.status_code == 200

    assert response.json()["comment"] == "Foo"
    blog_comment_hash = response.json()["hash"]
    assert blog_comment_hash
    assert BlogComment.objects.filter(blogitem=blogitem, comment="Foo").count() == 1

    response = client.post(
        url,
        {"oid": blogitem.oid, "comment": "Bar", "hash": "XXX"},
    )
    assert response.status_code == 403

    response = client.post(
        url,
        {"oid": blogitem.oid, "comment": "Bar", "hash": blog_comment_hash},
    )
    assert response.status_code == 200
    assert BlogComment.objects.filter(blogitem=blogitem, comment="Bar").count() == 1


@pytest.mark.django_db
def test_preview_comment(client):
    url = reverse("publicapi:preview_comment")

    response = client.post(
        url,
        {
            "comment": " ",
        },
    )
    assert response.status_code == 400

    response = client.post(
        url,
        {
            "comment": "x" * 10_001,
        },
    )
    assert response.status_code == 400

    response = client.post(
        url,
        {
            "comment": '<a href="http://example.com">example</a>',
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["comment"] == (
        '&lt;a href="<a href="http://example.com" '
        'rel="nofollow">http://example.com</a>"&gt;example&lt;/a&gt;'
    )
