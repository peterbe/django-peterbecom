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

    blog_file = BlogFile.objects.create(
        blogitem=blogitem, title="Some title", file=test_file
    )
    url = reverse("api:images", args=["hello-world"])
    response = admin_client.get(url)
    assert response.status_code == 200
    images = response.json()["images"]
    assert images
    (image,) = images
    assert image["id"] == blog_file.id
    assert image["full_url"]
    assert image["full_size"] == [1069, 661]
    for key in ("small", "big", "bigger"):
        assert image[key]
        assert image[key]["alt"] == "Some title"
        assert image[key]["height"]
        assert image[key]["width"]
        assert image[key]["url"]
