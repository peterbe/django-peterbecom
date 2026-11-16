import json

from django.urls import reverse


def test_chiveproxy_banned_url_patterns_happy_path(admin_client):
    url = reverse("api:chiveproxy_banned_url_patterns")
    response = admin_client.get(url)
    assert response.status_code == 200
    assert response.json() == {"patterns": []}

    response = admin_client.post(
        url,
        json.dumps(
            {
                "is_regex": False,
                "case_insensitive": "bla",
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 400

    response = admin_client.post(
        url,
        json.dumps(
            {
                "pattern": "example.com",
                "is_regex": False,
                "case_insensitive": True,
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 201

    response = admin_client.post(
        url,
        json.dumps(
            {
                "pattern": "[a-f0-9]{3}",
                "is_regex": True,
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 201

    response = admin_client.get(url)
    assert response.status_code == 200

    second, first = response.json()["patterns"]

    assert first["pattern"] == "example.com"
    assert first["is_regex"] is False
    assert first["case_insensitive"] is True
    assert first["kills"] == 0
    assert first["id"]
    assert first["created"]
    assert first["modified"]

    assert second["pattern"] == "[a-f0-9]{3}"
    assert second["is_regex"] is True
    assert second["case_insensitive"] is False
    assert second["kills"] == 0
    assert second["id"]
    assert second["created"]
    assert second["modified"]

    response = admin_client.delete(f"{url}?id={first['id']}")
    assert response.status_code == 200

    response = admin_client.get(url)
    assert response.status_code == 200
    assert len(response.json()["patterns"]) == 1
    assert response.json()["patterns"][0]["id"] == second["id"]
