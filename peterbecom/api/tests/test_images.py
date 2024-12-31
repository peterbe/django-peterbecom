import json
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from peterbecom.plog.models import BlogFile, BlogItem


def test_admin_required(client):
    url = reverse("api:images", args=["hello-world"])
    response = client.get(url)
    assert response.status_code == 403


def test_empty(admin_client):
    BlogItem.objects.create(
        oid="hello-world",
        title="Hello World",
        pub_date=timezone.now(),
        proper_keywords=["one", "two"],
    )
    url = reverse("api:images", args=["hello-world"])
    response = admin_client.get(url)
    assert response.status_code == 200
    assert response.json()["images"] == []


def test_happy_path(admin_client):
    blogitem = BlogItem.objects.create(
        oid="hello-world",
        title="Hello World",
        pub_date=timezone.now(),
        proper_keywords=["one", "two"],
    )
    with open(Path(__file__).parent / "test_image.png", "rb") as f:
        test_file = SimpleUploadedFile(
            "test_image.png", f.read(), content_type="image/png"
        )

    url = reverse("api:images", args=["hello-world"])

    response = admin_client.post(
        url, {"file": test_file, "title": "Some title"}, format="multipart"
    )

    response = admin_client.get(url)
    assert response.status_code == 200
    images = response.json()["images"]
    assert images
    (image,) = images
    assert image["id"]
    assert image["full_url"]
    assert image["full_size"] == [1069, 661]
    for key in ("small", "big", "bigger"):
        assert image[key]
        assert image[key]["alt"] == "Some title"
        assert image[key]["height"]
        assert image[key]["width"]
        assert image[key]["url"]

    response = admin_client.post(
        url,
        {"_update": True, "id": image["id"], "title": "New title"},
    )
    assert response.status_code == 200
    assert response.json()["ok"]
    response = admin_client.get(url)
    assert response.status_code == 200
    images = response.json()["images"]
    assert images[0]["big"]["alt"] == "New title"
    response = admin_client.patch(
        url,
    )
    assert response.status_code == 405

    blog_file = BlogFile.objects.get(blogitem=blogitem)
    response = admin_client.delete(f"{url}?id={blog_file.id}")
    assert response.status_code == 200
    assert response.json()["deleted"]


def test_upload_jpeg(admin_client, client):
    BlogItem.objects.create(
        oid="hello-world",
        title="Hello World",
        pub_date=timezone.now(),
        proper_keywords=["one", "two"],
    )
    with open(Path(__file__).parent / "test_image.jpg", "rb") as f:
        test_file = SimpleUploadedFile(
            "test_image.jpg", f.read(), content_type="image/jpeg"
        )

    url = reverse("api:images", args=["hello-world"])

    response = admin_client.post(
        url, {"file": test_file, "title": "Some title"}, format="multipart"
    )

    response = admin_client.get(url)
    assert response.status_code == 200
    images = response.json()["images"]
    assert images

    response = client.get(images[0]["full_url"])
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"

    response = client.get(images[0]["small"]["url"])
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"


def test_open_graph_image(admin_client):
    url = reverse("api:open_graph_image", args=["hello-world"])
    response = admin_client.get(url)
    assert response.status_code == 404

    blogitem = BlogItem.objects.create(
        oid="hello-world",
        title="Hello World",
        pub_date=timezone.now(),
        proper_keywords=["one", "two"],
    )
    response = admin_client.get(url)
    assert response.status_code == 200
    assert response.json() == {"images": []}

    response = admin_client.post(
        url,
        json.dumps(
            {
                "src": "garbage",
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 400

    with open(Path(__file__).parent / "test_image.png", "rb") as f:
        test_file = SimpleUploadedFile(
            "test_image.png", f.read(), content_type="image/png"
        )

    BlogFile.objects.create(blogitem=blogitem, title="Some title", file=test_file)
    response = admin_client.get(url)
    assert response.status_code == 200
    images = response.json()["images"]
    assert images

    response = admin_client.post(
        url,
        json.dumps(
            {
                "src": images[0]["src"],
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 200
    blogitem.refresh_from_db()
    assert blogitem.open_graph_image
