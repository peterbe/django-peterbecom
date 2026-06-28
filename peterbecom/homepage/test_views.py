import datetime

import pytest
import xmltodict
from django.urls import reverse
from django.utils import timezone

from peterbecom.homepage.models import CatchallURL
from peterbecom.plog.models import BlogItem, Category


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
