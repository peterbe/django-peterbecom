import json

from django.core.serializers.json import DjangoJSONEncoder
from django.urls import reverse
from django.utils import timezone

from peterbecom.plog.models import (
    BlogComment,
    BlogItem,
    Category,
)


def json_datetime(obj):
    return DjangoJSONEncoder().default(obj)


def test_admin_required(client):
    url = reverse("api:blogcomments")
    response = client.get(url)
    assert response.status_code == 403


def test_empty(admin_client):
    url = reverse("api:blogcomments")
    response = admin_client.get(url)
    assert response.status_code == 200
    assert response.json()["comments"] == []
    assert response.json()["count"] == 0


def test_happy_path(admin_client):
    blogitem = BlogItem.objects.create(
        oid="hello-world",
        title="Hello World",
        pub_date=timezone.now(),
        proper_keywords=["one", "two"],
    )
    category = Category.objects.create(name="Code")
    blogitem.categories.add(category)
    blogcomment = BlogComment.objects.create(
        oid="abc123",
        blogitem=blogitem,
        parent=None,
        approved=False,
        auto_approved=False,
        comment="Bla <bla>",
        name="John Doe",
        email="",
    )

    url = reverse("api:blogcomments")
    response = admin_client.get(url)
    assert response.status_code == 200
    assert response.json()["count"] == 1
    (first,) = response.json()["comments"]

    assert first["id"] == blogcomment.id
    assert first["oid"] == "abc123"
    assert first["blogitem"]["oid"] == "hello-world"
    assert first["blogitem"]["title"] == "Hello World"
    assert first["location"] is None
    assert first["page"] == 1
    assert first["comment"] == "Bla <bla>"
    assert first["rendered"] == "Bla &lt;bla&gt;"

    assert first["replies"] == []
    assert first["user_agent"] is None
    assert first["user_other_comments_count"] == 1


def test_replies(admin_client):
    blogitem = BlogItem.objects.create(
        oid="hello-world",
        title="Hello World",
        pub_date=timezone.now(),
        proper_keywords=["one", "two"],
    )
    blogcomment = BlogComment.objects.create(
        oid="abc123",
        blogitem=blogitem,
        parent=None,
        approved=False,
        auto_approved=False,
        comment="Bla <bla>",
        name="John Doe",
        email="",
    )
    reply = BlogComment.objects.create(
        oid="xyz123",
        blogitem=blogitem,
        parent=blogcomment,
        approved=False,
        auto_approved=False,
        comment="Bla <bla>",
        name="Replier",
        email="replier@example.com",
    )

    url = reverse("api:blogcomments")
    response = admin_client.get(url)
    assert response.status_code == 200
    assert response.json()["count"] == 2
    (first,) = response.json()["comments"]
    assert len(first["replies"]) == 1
    (first_reply,) = first["replies"]
    assert first_reply["id"] == reply.id


def test_search_by_blogitem(admin_client):
    blogitem1 = BlogItem.objects.create(
        oid="hello-world",
        title="Hello World",
        pub_date=timezone.now(),
    )
    blogcomment1 = BlogComment.objects.create(
        oid="abc123",
        blogitem=blogitem1,
        parent=None,
        approved=False,
        auto_approved=False,
        comment="Bla <bla>",
        name="John Doe",
        email="",
    )
    blogitem2 = BlogItem.objects.create(
        oid="foo-bar",
        title="Foo Bar",
        pub_date=timezone.now(),
    )
    blogcomment2 = BlogComment.objects.create(
        oid="xyz123",
        blogitem=blogitem2,
        parent=None,
        approved=False,
        auto_approved=False,
        comment="Fubar!",
        name="",
        email="",
        add_date=timezone.now() - timezone.timedelta(days=1),
        modify_date=timezone.now() - timezone.timedelta(days=1),
    )

    url = reverse("api:blogcomments")
    response = admin_client.get(url)
    assert response.status_code == 200
    assert response.json()["count"] == 2
    found = [x["id"] for x in response.json()["comments"]]
    assert found == [blogcomment1.id, blogcomment2.id]

    response = admin_client.get(url, {"search": "blogitem:foo-bar"})
    assert response.status_code == 200
    assert response.json()["count"] == 1
    found = [x["id"] for x in response.json()["comments"]]
    assert found == [blogcomment2.id]

    response = admin_client.get(url, {"search": "blogitem:!foo-bar"})
    assert response.status_code == 200
    assert response.json()["count"] == 1
    found = [x["id"] for x in response.json()["comments"]]
    assert found == [blogcomment1.id]

    response = admin_client.get(url, {"search": "oid:hello-world"})
    assert response.status_code == 200
    assert response.json()["count"] == 1
    found = [x["id"] for x in response.json()["comments"]]
    assert found == [blogcomment1.id]

    response = admin_client.get(url, {"search": "oid:never-heard-of"})
    assert response.status_code == 200
    assert response.json()["count"] == 0

    blogcomment3 = BlogComment.objects.create(
        oid="xyz890",
        blogitem=blogitem2,
        parent=None,
        approved=False,
        auto_approved=False,
        comment="Shampoo",
        name="",
        email="",
    )

    response = admin_client.get(url, {"search": "blogitem:foo-bar shampoo"})
    assert response.status_code == 200
    assert response.json()["count"] == 1
    found = [x["id"] for x in response.json()["comments"]]
    assert found == [blogcomment3.id]

    response = admin_client.get(url, {"search": "/plog/foo-bar"})
    assert response.status_code == 200
    assert response.json()["count"] == 2
    found = [x["id"] for x in response.json()["comments"]]
    assert found == [blogcomment3.id, blogcomment2.id]

    response = admin_client.get(url, {"search": "/plog/foo-bar SHAMPOO"})
    assert response.status_code == 200
    assert response.json()["count"] == 1
    found = [x["id"] for x in response.json()["comments"]]
    assert found == [blogcomment3.id]

    response = admin_client.get(
        url, {"search": "https://www.peterbe.com/plog/hello-world?a=b#abc"}
    )
    assert response.status_code == 200
    assert response.json()["count"] == 1
    found = [x["id"] for x in response.json()["comments"]]
    assert found == [blogcomment1.id]


def test_batch_submit_auth(client):
    url = reverse("api:blogcomments_batch", args=["both"])
    response = client.get(url)
    assert response.status_code == 403


def test_batch_submit(admin_client):
    url = reverse("api:blogcomments_batch", args=["both"])
    response = admin_client.get(url)
    assert response.status_code == 405

    response = admin_client.post(
        url,
        json.dumps(
            {
                "approve": [],
                "delete": [],
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["errors"]

    response = admin_client.post(
        url,
        json.dumps(
            {
                "approve": ["madeup"],
                "delete": ["doesnotexist"],
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["errors"]["approve"]
    assert response.json()["errors"]["delete"]

    blogitem = BlogItem.objects.create(
        oid="hello-world",
        title="Hello World",
        pub_date=timezone.now(),
        proper_keywords=["one", "two"],
    )
    blogcomment1 = BlogComment.objects.create(
        oid="abc123",
        blogitem=blogitem,
        parent=None,
        approved=False,
        auto_approved=False,
        comment="Bla <bla>",
        email="",
        name="John Doe",
    )
    blogcomment2 = BlogComment.objects.create(
        oid="xyz123",
        blogitem=blogitem,
        parent=None,
        approved=False,
        auto_approved=False,
        comment="Fubar!",
        name="",
        email="",
        add_date=timezone.now() - timezone.timedelta(days=1),
        modify_date=timezone.now() - timezone.timedelta(days=1),
    )

    response = admin_client.post(
        url,
        json.dumps(
            {
                "approve": [blogcomment1.oid],
                "delete": [blogcomment2.oid],
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["approved"] == [blogcomment1.oid]
    assert response.json()["deleted"] == [blogcomment2.oid]

    blogcomment1.refresh_from_db()
    assert blogcomment1.approved

    assert not BlogComment.objects.filter(oid=blogcomment2.oid).exists()
