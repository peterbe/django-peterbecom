import datetime

import pytest
import xmltodict
from django.urls import reverse
from django.utils import timezone

from peterbecom.plog.models import BlogItem, Category


@pytest.mark.django_db
def test_rss_xml_happy_path(client):
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
def test_rss_xml_include_photos(client):
    BlogItem.objects.create(
        oid="foo-bar",
        title="Foo Bar",
        pub_date=timezone.now() + datetime.timedelta(days=1),
    )
    BlogItem.objects.create(
        oid="hello-world",
        title="Hello",
        pub_date=timezone.now() - datetime.timedelta(days=1),
        text="Hullo",
        summary="This is the summary",
    )
    BlogItem.objects.create(
        oid="archived",
        title="Archived",
        pub_date=timezone.now() - datetime.timedelta(days=1),
        text="Hullo",
        summary="This is the summary",
        archived=timezone.now(),
    )
    BlogItem.objects.create(
        oid="photo1",
        title="Photo 1",
        pub_date=timezone.now() - datetime.timedelta(days=1),
        text="",
        is_photo=True,
    )
    BlogItem.objects.create(
        oid="photo2",
        title="Photo 2",
        pub_date=timezone.now() - datetime.timedelta(days=1),
        text="Hullo",
        is_photo=True,
        archived=timezone.now(),
    )

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
    assert len(items) == 2

    assert items[0]["title"] == "Photo 1"
    assert items[0]["link"] == "http://example.com/photos/photo1"
    assert items[1]["title"] == "Hello"
    assert items[1]["link"] == "http://example.com/plog/hello-world"


@pytest.mark.django_db
def test_rss_xml_absolute_urls_in_summary(client):
    blogitem = BlogItem.objects.create(
        oid="foo-bar",
        title="Foo Bar",
        pub_date=timezone.now() - datetime.timedelta(days=1),
        summary="",
        text="""[![foo](/cache/foo/bar.jpg)](/plog/foo-bar)""",
        display_format="markdown",
    )
    assert blogitem._render()
    blogitem.refresh_from_db()
    assert '<img alt="foo" src="/cache/foo/bar.jpg" />' in blogitem.rendered

    blogitem2 = BlogItem.objects.create(
        oid="hello-world",
        title="Hello World",
        pub_date=timezone.now() - datetime.timedelta(days=2),
        summary="",
        text_rendered="""<p>
        <img src="//cdn.peterbe.com/images/image.png">
        </p>""",
    )
    assert blogitem2._render()
    blogitem2.refresh_from_db()
    assert '<img src="//cdn.peterbe.com/images/image.png">' in blogitem2.rendered

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

    assert len(items) == 2

    assert items[0]["title"] == "Foo Bar"
    assert 'src="https://www.peterbe.com/cache/foo/bar.jpg"' in items[0]["description"]
    assert items[1]["title"] == "Hello World"
    assert 'src="https://cdn.peterbe.com/images/image.png"' in items[1]["description"]
