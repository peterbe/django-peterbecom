import json

from django.urls import reverse


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
