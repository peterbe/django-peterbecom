import re
import shutil

import pytest
from django.conf import settings
from django.urls import reverse


@pytest.fixture(scope="module", autouse=True)
def after_tests():
    yield

    assert settings.IMAGE_PROXY_CACHE_ROOT.name.startswith("test_")
    shutil.rmtree(settings.IMAGE_PROXY_CACHE_ROOT)


def test_image_proxy_errors(client):
    url = reverse("chiveproxy:image_proxy")
    response = client.get(url)
    assert response.status_code == 400
    response = client.get(url, {"url": ""})
    assert "This field is required" in response.content.decode("utf-8")
    assert response.status_code == 400
    response = client.get(url, {"url": "junk"})
    assert "Enter a valid URL" in response.content.decode("utf-8")
    assert response.status_code == 400

    response = client.get(url, {"url": "https://www.example.com/uploads/test.jpg"})
    assert response.status_code == 400
    assert "Invalid netloc" in response.content.decode("utf-8")

    response = client.get(url, {"url": "http://choive.com/content/test.jpg"})
    assert response.status_code == 400
    assert "not https" in response.content.decode("utf-8")

    response = client.get(url, {"url": "https://choive.com/content/test.bmp"})
    assert response.status_code == 400
    assert "Invalid file extension" in response.content.decode("utf-8")


def test_image_proxy_happy_path(client, requestsmock):
    with open("peterbecom/chiveproxy/tests/test_image.jpg", "rb") as f:
        requestsmock.get("https://choive.com/content/test.jpg", content=f.read())
    url = reverse("chiveproxy:image_proxy")
    response = client.get(url, {"url": "https://choive.com/content/test.jpg"})
    assert response.status_code == 200
    assert response["Content-Type"] == "image/webp"
    assert "public" in response["Cache-Control"]
    assert "max-age=" in response["Cache-Control"]
    assert "max-age=0" not in response["Cache-Control"]


def test_image_proxy_png(client, requestsmock):
    with open("peterbecom/chiveproxy/tests/test_image.png", "rb") as f:
        requestsmock.get("https://choive.com/content/test.png", content=f.read())
    url = reverse("chiveproxy:image_proxy")
    response = client.get(url, {"url": "https://choive.com/content/test.png"})
    assert response.status_code == 200
    assert response["Content-Type"] == "image/webp"
    assert "public" in response["Cache-Control"]
    assert "max-age=" in response["Cache-Control"]
    assert "max-age=0" not in response["Cache-Control"]


def test_image_proxy_webp(client, requestsmock):
    with open("peterbecom/chiveproxy/tests/test_image.webp", "rb") as f:
        requestsmock.get("https://choive.com/content/test.webp", content=f.read())
    url = reverse("chiveproxy:image_proxy")
    response = client.get(url, {"url": "https://choive.com/content/test.webp"})
    assert response.status_code == 200
    assert response["Content-Type"] == "image/webp"
    assert "public" in response["Cache-Control"]
    assert "max-age=" in response["Cache-Control"]
    assert "max-age=0" not in response["Cache-Control"]


def test_image_proxy_redirect_to_file(client, requestsmock):
    with open("peterbecom/chiveproxy/tests/test_image.jpg", "rb") as f:
        requestsmock.get("https://choive.com/content/test.jpg", content=f.read())
    url = reverse("chiveproxy:image_proxy")
    response = client.get(
        url, {"url": "https://choive.com/content/test.jpg", "redirect_to_file": True}
    )
    assert response.status_code == 302
    assert re.findall(
        r"/image_proxy/\w{2}/\w{2}/test-\w{8}\.webp", response["Location"]
    )
    assert "public" in response["Cache-Control"]
    assert "max-age=" in response["Cache-Control"]
    assert "max-age=0" not in response["Cache-Control"]
