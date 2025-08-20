import json

from django.urls import reverse
from django.utils import timezone

from peterbecom.plog.models import BlogComment, BlogItem, SpamCommentPattern


def test_admin_required(client):
    url = reverse("api:spam_signatures")
    response = client.get(url)
    assert response.status_code == 403

    url = reverse("api:spam_patterns")
    response = client.get(url)
    assert response.status_code == 403


def test_empty(admin_client):
    url = reverse("api:spam_signatures")
    response = admin_client.get(url)
    assert response.status_code == 200
    assert response.json() == {"signatures": []}

    url = reverse("api:spam_patterns")
    response = admin_client.get(url)
    assert response.status_code == 200
    assert response.json() == {"patterns": []}


def test_happy_path_signatures(admin_client):
    url = reverse("api:spam_signatures")

    response = admin_client.post(
        url,
        json.dumps(
            {
                "name": "peter",
                "name_null": False,
                "email": "",
                "email_null": True,
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 200

    response = admin_client.get(url)
    assert response.status_code == 200

    signatures = response.json()["signatures"]
    assert signatures
    (first,) = signatures
    assert first["id"]
    assert first["email"] is None
    assert first["name"] == "peter"
    assert first["kills"] == 0
    assert first["add_date"]
    assert first["modify_date"]

    response = admin_client.delete(f"{url}?id={first['id']}")
    assert response.status_code == 200
    response = admin_client.get(url)
    assert response.status_code == 200
    assert not response.json()["signatures"]


def test_bad_request_signatures(admin_client):
    url = reverse("api:spam_signatures")
    response = admin_client.post(
        url,
        {"not": "json"},
    )
    assert response.status_code == 400
    response = admin_client.post(
        url,
        json.dumps(
            {
                # No name!
                "name_null": False,
                "email": "",
                "email_null": True,
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 400

    response = admin_client.delete(f"{url}?id=999999")
    assert response.status_code == 404


def test_happy_path_patterns(admin_client):
    url = reverse("api:spam_patterns")

    response = admin_client.post(
        url,
        json.dumps(
            {
                "pattern": "spell?s",
                "is_regex": True,
                "is_url_pattern": False,
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 200

    response = admin_client.get(url)
    assert response.status_code == 200

    signatures = response.json()["patterns"]
    assert signatures
    (first,) = signatures
    assert first["id"]
    assert first["pattern"] == "spell?s"
    assert first["is_regex"] is True
    assert first["is_url_pattern"] is False
    assert first["kills"] == 0
    assert first["add_date"]
    assert first["modify_date"]

    response = admin_client.delete(f"{url}?id={first['id']}")
    assert response.status_code == 200
    response = admin_client.get(url)
    assert response.status_code == 200
    assert not response.json()["patterns"]


def test_bad_request_patterns(admin_client):
    url = reverse("api:spam_patterns")
    response = admin_client.post(
        url,
        {"not": "json"},
    )
    assert response.status_code == 400
    response = admin_client.post(
        url,
        json.dumps(
            {
                # No pattern!
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 400

    response = admin_client.delete(f"{url}?id=999999")
    assert response.status_code == 404


def test_execute_spam_pattern_auth(client):
    url = reverse("api:execute_pattern", args=["9999"])
    response = client.post(
        url,
        {"not": "json"},
    )
    assert response.status_code == 403


def test_execute_spam_pattern_happy(admin_client):
    blogitem = BlogItem.objects.create(
        oid="hello-world",
        title="Hello World",
        pub_date=timezone.now(),
        proper_keywords=["one", "two"],
    )

    BlogComment.objects.create(
        oid="abc1",
        blogitem=blogitem,
        parent=None,
        approved=False,
        auto_approved=False,
        comment="bar and foo",
        name="John Doe",
        email="",
    )
    BlogComment.objects.create(
        oid="abc2",
        blogitem=blogitem,
        parent=None,
        approved=False,
        auto_approved=False,
        comment="pern is a word",
        name="John Doe",
        email="",
    )
    BlogComment.objects.create(
        oid="abc3",
        blogitem=blogitem,
        parent=None,
        approved=False,
        auto_approved=False,
        comment="Neither match not FoO or puurn",
        name="John Doe",
        email="",
    )
    url = reverse("api:execute_pattern", args=["9999"])
    response = admin_client.post(url)
    assert response.status_code == 404

    pattern1 = SpamCommentPattern.objects.create(
        pattern="foo", is_regex=False, is_url_pattern=False
    )
    pattern2 = SpamCommentPattern.objects.create(
        pattern=r"p\wrn", is_regex=True, is_url_pattern=False
    )

    url = reverse("api:execute_pattern", args=[pattern1.id])
    response = admin_client.post(url)
    assert response.status_code == 200

    assert response.json()["limit"]
    assert response.json()["executions"] == [
        {"matched": False, "approved": False, "regex": None},
        {"matched": False, "approved": False, "regex": None},
        {"matched": True, "approved": False, "regex": False},
    ]

    url = reverse("api:execute_pattern", args=[pattern2.id])
    response = admin_client.post(url)
    assert response.status_code == 200

    assert response.json()["limit"]
    assert response.json()["executions"] == [
        {"matched": False, "approved": False, "regex": None},
        {"matched": True, "approved": False, "regex": True},
        {"matched": False, "approved": False, "regex": None},
    ]
