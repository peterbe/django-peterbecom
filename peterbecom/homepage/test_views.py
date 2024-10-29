import datetime
import re
from urllib.parse import urlparse

import pytest
import xmltodict
from django.urls import reverse
from django.utils import timezone

from peterbecom.homepage.models import CatchallURL
from peterbecom.plog.models import BlogItem, BlogItemDailyHits, Category


@pytest.mark.django_db
def test_sitemap(client):
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


@pytest.mark.django_db
def test_rss_xml(client):
    BlogItem.objects.create(
        oid="foo-bar",
        title="Foo Bar",
        pub_date=timezone.now() + datetime.timedelta(days=1),
    )
    blogitem1 = BlogItem.objects.create(
        oid="hello-world",
        title="Hello",
        pub_date=timezone.now() - datetime.timedelta(days=1),
        text="Hullo",
    )
    blogitem2 = BlogItem.objects.create(
        oid="more-popular",
        title="More popular",
        pub_date=timezone.now() - datetime.timedelta(days=2),
        text="Popular",
    )
    cat2 = Category.objects.create(name="Two")
    cat1 = Category.objects.create(name="One")
    blogitem1.categories.add(cat1)
    blogitem2.categories.add(cat1)
    blogitem2.categories.add(cat2)

    url = reverse(
        "homepage:rss_redirect",
        args={
            "",
        },
    )
    response = client.get(url)
    assert response.status_code == 302
    assert response["location"] == "http://testserver/rss.xml"

    url = reverse("homepage:rss", args=("",))
    response = client.get(url)
    assert response.status_code == 200
    payload = response.content.decode("utf-8")
    parsed = xmltodict.parse(payload)

    items = parsed["rss"]["channel"]["item"]

    assert items[0]["title"] == "Hello"
    assert items[0]["description"] == "<p>Hullo</p>"
    assert items[0]["pubDate"]
    assert items[0]["link"] == "http://example.com/plog/hello-world"
    assert items[0]["link"] == items[0]["guid"]

    guids = [item["guid"] for item in items]
    assert guids == [
        "http://example.com/plog/hello-world",
        "http://example.com/plog/more-popular",
    ]
    url = reverse(
        "homepage:rss",
        args={
            "Two",
        },
    )
    response = client.get(url)
    assert response.status_code == 200
    payload = response.content.decode("utf-8")
    assert "hello-world" not in payload
    assert "more-popular" in payload

    url = reverse(
        "homepage:rss",
        args={
            "",
        },
    )
    response = client.get(url, {"oc": "One"})
    assert response.status_code == 200
    payload = response.content.decode("utf-8")
    parsed = xmltodict.parse(payload)

    items = parsed["rss"]["channel"]["item"]
    guids = [item["guid"] for item in items]
    assert guids == [
        "http://example.com/plog/hello-world",
        "http://example.com/plog/more-popular",
    ]


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
