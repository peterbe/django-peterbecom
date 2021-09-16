from django.urls import reverse

from peterbecom.base.models import UserProfile


def test_whoami_anonymous(client):
    url = reverse("api:whoami")
    response = client.get(url)
    assert response.status_code == 200
    assert not response.json()["is_authenticated"]


def test_whoami_logged_in_admin(admin_client):
    url = reverse("api:whoami")
    response = admin_client.get(url)
    assert response.status_code == 200
    assert response.json()["is_authenticated"]
    assert response.json()["user"]["is_superuser"]


def test_whoami_logged_in_mortal(mortal_client):
    url = reverse("api:whoami")
    response = mortal_client.get(url)
    assert response.status_code == 200
    assert response.json()["is_authenticated"]
    assert not response.json()["user"]["is_superuser"]


def test_whoami_with_picture(mortal_client, mortal_user):
    UserProfile.objects.create(
        user=mortal_user, claims={"picture": "https://avatars.example.com/pic"}
    )
    url = reverse("api:whoami")
    response = mortal_client.get(url)
    assert response.status_code == 200
    assert response.json()["is_authenticated"]
    response.json()["user"]["picture_url"] == "https://avatars.example.com/pic"
