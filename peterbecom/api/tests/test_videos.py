import os
import shutil
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from peterbecom.plog.models import BlogFile, BlogItem

executable_path = shutil.which("ffmpeg")
HAS_FFMPEG = executable_path and os.access(executable_path, os.X_OK)


def test_admin_required(client):
    url = reverse("api:videos", args=["hello-world"])
    response = client.get(url)
    assert response.status_code == 403


def test_empty(admin_client):
    BlogItem.objects.create(
        oid="hello-world",
        title="Hello World",
        pub_date=timezone.now(),
        proper_keywords=["one", "two"],
    )
    url = reverse("api:videos", args=["hello-world"])
    response = admin_client.get(url)
    assert response.status_code == 200
    assert response.json()["videos"] == []


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg not executable")
def test_happy_path(admin_client):
    blogitem = BlogItem.objects.create(
        oid="hello-world",
        title="Hello World",
        pub_date=timezone.now(),
        proper_keywords=["one", "two"],
    )
    with open(Path(__file__).parent / "test_video.mov", "rb") as f:
        test_file = SimpleUploadedFile(
            "test_video.mov", f.read(), content_type="image/mov"
        )

    url = reverse("api:videos", args=["hello-world"])

    response = admin_client.post(
        url, {"file": test_file, "title": "Some title"}, format="multipart"
    )

    response = admin_client.get(url)
    assert response.status_code == 200
    videos = response.json()["videos"]
    assert videos
    (video,) = videos
    assert video["id"]
    assert video["thumbnails"]
    for key in ("big", "bigger", "full"):
        assert video["thumbnails"][key]
        assert video["thumbnails"][key]["alt"] == "Some title"
        assert video["thumbnails"][key]["height"]
        assert video["thumbnails"][key]["width"]
        assert video["thumbnails"][key]["url"]
    assert video["formats"]
    for key in ("mov", "mp4", "webm"):
        assert video["formats"][key]
        assert video["formats"][key]["type"]
        assert video["formats"][key]["url"].startswith("/")

    response = admin_client.post(
        url,
        {"_update": True, "id": video["id"], "title": "New title"},
    )
    assert response.status_code == 200
    assert response.json()["ok"]
    response = admin_client.get(url)
    assert response.status_code == 200
    videos = response.json()["videos"]
    (video,) = videos
    assert video["thumbnails"]["big"]["alt"] == "New title"
    response = admin_client.patch(
        url,
    )
    assert response.status_code == 405

    blog_file = BlogFile.objects.get(blogitem=blogitem)
    response = admin_client.delete(f"{url}?id={blog_file.id}")
    assert response.status_code == 200
    assert response.json()["deleted"]
