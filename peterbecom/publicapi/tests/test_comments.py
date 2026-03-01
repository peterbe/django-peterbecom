import pytest
from django.urls import reverse
from django.utils import timezone

from peterbecom.plog.models import (
    BlogComment,
    BlogItem,
    SpamCommentPattern,
    SpamCommentSignature,
)


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
def test_spamy_comment(client):
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
    pattern = SpamCommentPattern.objects.create(
        is_url_pattern=True,
        pattern="example.com",
    )
    response = client.post(
        url,
        {"oid": blogitem.oid, "comment": "Comment text http://example.com"},
    )
    assert response.status_code == 400
    assert response.content.decode("utf-8") == "Looks too spammy"
    pattern.refresh_from_db()
    assert pattern.kills == 1

    pattern = SpamCommentPattern.objects.create(
        pattern="skype",
    )
    response = client.post(
        url,
        {"oid": blogitem.oid, "comment": "Don't mention skype"},
    )
    assert response.status_code == 400
    assert response.content.decode("utf-8") == "Looks too spammy"
    pattern.refresh_from_db()
    assert pattern.kills == 1


@pytest.mark.django_db
def test_spamy_custom_comment(client):
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
        {"oid": blogitem.oid, "comment": "OfcrPkOaz9oJwwWYaLhtsCp\n"},
    )
    assert response.status_code == 400
    assert response.content.decode("utf-8") == "Looks too spammy"

    response = client.post(
        url,
        {"oid": blogitem.oid, "comment": "LondonUndergroundStation\n"},
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_trash_commenter(client):
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
    signature = SpamCommentSignature.objects.create(
        name="John Doe", email="john@example.com"
    )
    response = client.post(
        url,
        {
            "oid": blogitem.oid,
            "comment": "Comment text",
            "name": "John Doe",
            "email": "john@example.com",
        },
    )
    assert response.status_code == 400
    assert response.json()["trash"]
    signature.refresh_from_db()
    assert signature.kills == 1

    signature.name = None
    signature.save()
    response = client.post(
        url,
        {
            "oid": blogitem.oid,
            "comment": "Comment text",
            "name": "Whatever",
            "email": "john@example.com",
        },
    )
    assert response.status_code == 400
    assert response.json()["trash"]
    signature.refresh_from_db()
    assert signature.kills == 2

    signature.email = None
    signature.name = "John Doe"
    signature.save()
    response = client.post(
        url,
        {
            "oid": blogitem.oid,
            "comment": "Comment text",
            "name": "John Doe",
            "email": "",
        },
    )
    assert response.status_code == 400
    assert response.json()["trash"]
    signature.refresh_from_db()
    assert signature.kills == 3

    signature.delete()
    response = client.post(
        url,
        {
            "oid": blogitem.oid,
            "comment": "Comment text",
            "name": "John Doe",
            "email": "john@example.com",
        },
    )
    assert response.status_code == 200


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
def test_submit_with_long_name_and_email(client):
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
            "name": "x" * 101,
            "email": "",
        },
    )
    assert response.status_code == 400
    error = response.json()
    assert error["error"]["name"]

    response = client.post(
        url,
        {
            "oid": blogitem.oid,
            "comment": "Comment text ",
            "name": "Tester",
            "email": "x" * 100 + "test@example.com",
        },
    )
    assert response.status_code == 400
    error = response.json()
    assert error["error"]["email"]


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
def test_submit_comment_twice(client):
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
            "name": "John Doe",
        },
    )
    assert response.status_code == 200
    BlogComment.objects.filter(blogitem=blogitem).count() == 1

    response = client.post(
        url,
        {
            "oid": blogitem.oid,
            "comment": "Foo",
            "name": "John Doe",
        },
    )
    assert response.status_code == 200
    BlogComment.objects.filter(blogitem=blogitem).count() == 1  # still!


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


@pytest.mark.django_db
def test_prepare_comment(client):
    url = reverse("publicapi:prepare_comment")
    response = client.get(url)
    assert response.status_code == 200
    assert response.json()["csrfmiddlewaretoken"]


@pytest.mark.django_db
def test_submit_comment_with_invalid_url(client):
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
            "comment": "Please help me, I'm trying to identify the song ...here:\nhttps:/youtube.com/watch?v=abc123&t=25",
            "name": "John Doe",
            "email": "example@exmple.com ",
        },
    )
    assert response.status_code == 200

    # The point is that the badly formed URL does not become a link.
    # Nor does its presence cause an exception; the comment is saved.
    assert response.json()["comment"] == (
        "Please help me, I'm trying to identify the song ...here:<br>https:/youtube.com/watch?v=abc123&amp;t=25"
    )
    assert BlogComment.objects.filter(blogitem=blogitem).count() == 1
