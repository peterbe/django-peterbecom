import pytest

from django.urls import reverse
from django.contrib.auth import get_user_model


@pytest.mark.django_db
def test_blogitems_auth_fail(client, requestsmock, settings):
    url = reverse("api:blogitems")
    response = client.get(url)
    assert response.status_code == 403
    # Now with a bogus token
    response = client.get(url, HTTP_AUTHORIZATION="junk")
    assert response.status_code == 403

    response = client.get(url, HTTP_AUTHORIZATION="junk")
    assert response.status_code == 403

    requestsmock.get(settings.OIDC_USER_ENDPOINT, json={"email": "peterbe@peterbe.com"})

    response = client.get(url, HTTP_AUTHORIZATION="Bearer fine")
    assert response.status_code == 403


@pytest.mark.django_db
def test_blogitems_auth_works(client, requestsmock, settings, cache):
    url = reverse("api:blogitems")

    requestsmock.get(settings.OIDC_USER_ENDPOINT, json={"email": "peterbe@peterbe.com"})

    get_user_model().objects.create(
        email="peterbe@peterbe.com", is_superuser=True, username="whatever"
    )
    u, = get_user_model().objects.all()
    assert u.is_superuser
    response = client.get(url, HTTP_AUTHORIZATION="Bearer fine")
    assert response.status_code == 200, response.json()

    # Very basic, but something
    assert "blogitems" in response.json()
    assert response.json()["count"] == 0
