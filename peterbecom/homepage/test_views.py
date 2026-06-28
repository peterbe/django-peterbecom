import pytest
from django.urls import reverse

from peterbecom.homepage.models import CatchallURL


def test_old_alias(client):
    url = reverse("homepage:catchall", args=("10-reasons-for-web-standards",))
    response = client.get(url)
    assert response.status_code == 301
    assert response["Location"] == "/plog/blogitem-040606-1"


def test_robots_txt(client):
    url = reverse("homepage:robots_txt")
    response = client.get(url)
    assert response.status_code == 200
    assert response["content-type"] == "text/plain"
    assert response.text == "User-agent: *\nAllow: /\n"


@pytest.mark.django_db
def test_avatar_png(client):
    url = reverse("homepage:avatar_image")
    response = client.get(url)
    assert response.status_code == 200
    assert response["content-type"] == "image/png"

    seeded_url = reverse("homepage:avatar_image_seed", args=("random",))

    response = client.get(url, {"any": "qs"})
    assert response.status_code == 302
    assert response["location"] == seeded_url


@pytest.mark.django_db
def test_catchall(client):
    url = reverse("homepage:catchall", args=("foo",))
    response = client.get(url)
    assert response.status_code == 404
    caught = CatchallURL.objects.get(path="foo")
    assert caught.count == 1

    response = client.get(url)
    assert response.status_code == 404
    caught.refresh_from_db()
    assert caught.count == 2

    url = reverse("homepage:catchall", args=("crap.php",))
    response = client.get(url)
    assert response.status_code == 404
    assert not CatchallURL.objects.filter(path="crap.php").exists()
