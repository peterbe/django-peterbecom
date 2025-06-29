import json
from django.urls import reverse


def test_catch_all_auth(client):
    url = reverse("api:catch_all")
    response = client.get(url)
    assert response.status_code == 403


def test_catch_all_any(admin_client):
    url = reverse("api:catch_all")
    response = admin_client.get(url)
    assert response.status_code == 404


def test_probe_url_admin_required(client):
    url = reverse("api:probe_url")
    response = client.get(url)
    assert response.status_code == 403


def test_probe_url_fail(admin_client):
    url = reverse("api:probe_url")
    response = admin_client.get(url)
    assert response.status_code == 405
    response = admin_client.post(
        url,
        json.dumps({}),
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["errors"]
    assert response.json()["errors"]["url"]


def test_probe_url_happy_path(admin_client):
    url = reverse("api:probe_url")
    response = admin_client.post(
        url,
        json.dumps(
            {
                "url": "https://www.peterbe.com/about",
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["request"]
    assert data["request"]["url"]
    assert data["request"]["method"]
    assert data["request"]["user_agent"]
    assert data["response"]["status_code"] == 200
    assert data["response"]["body"]

    response = admin_client.post(
        url,
        json.dumps(
            {
                "url": "https://www.peterbe.com/plog/",
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["response"]["status_code"] == 302
    assert data["response"]["location"] == "/plog"
