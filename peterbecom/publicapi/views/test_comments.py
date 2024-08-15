import pytest
from django.urls import reverse
from django.utils import timezone

from peterbecom.plog.models import BlogComment, BlogItem


@pytest.mark.django_db
def test_submit_comment(client):
    url = reverse("publicapi:submit_comment")
    response = client.get(url)
    assert response.status_code == 405

    blog_item = BlogItem.objects.create(
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
            "oid": blog_item.oid,
        },
    )
    assert response.status_code == 400
    error = response.json()

    assert error["error"]["comment"]

    response = client.post(url, {"oid": blog_item.oid, "comment": "Comment text "})
    assert response.status_code == 200

    assert response.json()["comment"] == "Comment text"
    assert BlogComment.objects.filter(blogitem=blog_item).count() == 1


@pytest.mark.django_db
def test_submit_comment_x_forward_for(client):
    url = reverse("publicapi:submit_comment")
    blog_item = BlogItem.objects.create(
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
        {"oid": blog_item.oid, "comment": "Comment text "},
        headers={
            "x-forwarded-for": "2601:201:8a7e:38e0:79f6:4326:ff50:23b3, 68.70.197.65"
        },
    )
    assert response.status_code == 200
    data = response.json()

    blog_comment = BlogComment.objects.get(blogitem=blog_item, oid=data["oid"])
    assert blog_comment.ip_address == "2601:201:8a7e:38e0:79f6:4326:ff50:23b3"
