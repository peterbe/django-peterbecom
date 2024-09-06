import json

from django.urls import reverse


def test_preview_blogitem_happy_path(admin_client):
    url = reverse("api:preview")
    response = admin_client.post(
        url,
        json.dumps(
            {
                "text": "Hello *world*",
                "display_format": "markdown",
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 200


def test_preview_blogitem_validation_error(admin_client):
    url = reverse("api:preview")
    response = admin_client.post(
        url,
        json.dumps(
            {
                # "text": "Hello *world*",
                "display_format": "markdown",
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["blogitem"]["errors"]["text"]


def test_preview_blogitem_unauth(client):
    url = reverse("api:preview")
    response = client.post(
        url,
        json.dumps(
            {
                "text": "Hello *world*",
                "display_format": "markdown",
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 403


def test_preview_blogitem_require_post(admin_client):
    url = reverse("api:preview")
    response = admin_client.get(url)
    assert response.status_code == 405
