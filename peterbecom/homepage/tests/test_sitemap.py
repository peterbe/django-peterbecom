import datetime
import re
from urllib.parse import urlparse

import pytest
import xmltodict
from django.urls import reverse
from django.utils import timezone

from peterbecom.plog.models import BlogComment, BlogItem, BlogItemDailyHits


@pytest.mark.django_db
def test_sitemap_happy_path(client):
    BlogItem.objects.create(
        oid="foo-bar",
        title="Foo Bar",
        pub_date=timezone.now() + datetime.timedelta(days=1),
    )
    BlogItem.objects.create(
        oid="hello-world",
        title="Hello",
        pub_date=timezone.now() - datetime.timedelta(days=1),
    )
    more_popular = BlogItem.objects.create(
        oid="more-popular",
        title="More popular",
        pub_date=timezone.now() - datetime.timedelta(days=2),
    )
    BlogItemDailyHits.objects.create(
        blogitem=more_popular,
        date=timezone.now() - datetime.timedelta(days=1),
        total_hits=100,
    )

    url = reverse("homepage:sitemap")
    response = client.get(url)
    assert response.status_code == 200
    assert re.findall(r"public, max-age=\d\d+", response["cache-control"])

    payload = response.content.decode("utf-8")
    parsed = xmltodict.parse(payload)

    urls = parsed["urlset"]["url"]
    paths = [urlparse(url["loc"]).path for url in urls]
    assert paths[0] == "/"
    assert paths[1] == "/about"
    assert paths[2] == "/contact"
    assert paths[3] == "/plog/blogitem-040601-1"

    assert "/plog/hello-world" in paths
    assert "/plog/foo-bar" not in paths
    assert paths.index("/plog/more-popular") < paths.index("/plog/hello-world")


def test_sitemap_redirects_on_query_strings(client):
    url = reverse("homepage:sitemap")
    response = client.get(url, {"foo": "bar"})
    assert response.status_code == 302
    assert response["location"] == f"http://testserver{url}"


@pytest.mark.django_db
def test_sitemap_include_photos(client):
    BlogItem.objects.create(
        oid="foo-bar",
        title="Foo Bar",
        pub_date=timezone.now() + datetime.timedelta(days=1),  # future
    )
    BlogItem.objects.create(
        oid="hello-world",
        title="Hello",
        pub_date=timezone.now() - datetime.timedelta(days=1),
    )
    more_popular = BlogItem.objects.create(
        oid="more-popular",
        title="More popular",
        pub_date=timezone.now() - datetime.timedelta(days=2),
    )
    BlogItemDailyHits.objects.create(
        blogitem=more_popular,
        date=timezone.now() - datetime.timedelta(days=1),
        total_hits=100,
    )
    photo1 = BlogItem.objects.create(
        oid="myphoto",
        title="Photo",
        pub_date=timezone.now() - datetime.timedelta(days=0.5),
        is_photo=True,
    )
    photo2 = BlogItem.objects.create(
        oid="other-photo",
        title="OtherPhoto",
        pub_date=timezone.now() - datetime.timedelta(days=1.5),
        is_photo=True,
    )
    photo3 = BlogItem.objects.create(
        oid="other-photo-but-archived",
        title="OtherPhoto But Archived",
        pub_date=timezone.now() - datetime.timedelta(days=1.5),
        is_photo=True,
        archived=timezone.now(),
    )
    BlogComment.objects.create(
        oid="comment1",
        blogitem=photo1,
        approved=True,
    )
    BlogComment.objects.create(
        oid="comment2",
        blogitem=photo2,
        approved=True,
    )
    BlogComment.objects.create(
        oid="comment3",
        blogitem=photo3,
        approved=True,
    )

    url = reverse("homepage:sitemap")
    response = client.get(url)

    payload = response.content.decode("utf-8")
    parsed = xmltodict.parse(payload)

    urls = parsed["urlset"]["url"]
    paths = [urlparse(url["loc"]).path for url in urls]

    assert "/plog/foo-bar" not in paths  # future
    assert "/plog/hello-world" in paths
    assert "/photos/other-photo" in paths
    assert "/plog/other-photo" not in paths
    assert "/photos/other-photo-but-archived" not in paths
    assert "/plog/other-photo-but-archived" not in paths
