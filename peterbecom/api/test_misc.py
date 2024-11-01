from django.urls import reverse


def test_catch_all_auth(client):
    url = reverse("api:catch_all")
    response = client.get(url)
    assert response.status_code == 403


def test_catch_all_any(admin_client):
    url = reverse("api:catch_all")
    response = admin_client.get(url)
    assert response.status_code == 404
