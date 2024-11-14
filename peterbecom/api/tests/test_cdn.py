import requests_mock
from django.urls import reverse
from django.utils import timezone

from peterbecom.plog.models import BlogItem


def test_cdn_probe(admin_client):
    url = reverse("api:cdn_probe")
    response = admin_client.get(url)
    assert response.status_code == 400
    with requests_mock.Mocker() as m:
        m.get("http://testserver", text="Hi", headers={"X-Cache": "HIT"})
        response = admin_client.get(url, {"url": "/"})
        assert response.status_code == 200
        data = response.json()
        assert data["absolute_url"] == "http://testserver/"
        assert data["http_1"]["headers"]["X-Cache"] == "HIT"
        assert data["http_1"]["status_code"] == 200
        assert data["http_1"]["took"]
        assert data["http_1"]["x_cache"] == "HIT"

    BlogItem.objects.create(
        oid="hello-world",
        title="Hello World",
        pub_date=timezone.now(),
        proper_keywords=["one", "two"],
    )
    with requests_mock.Mocker() as m:
        m.get(
            "http://peterbecom.local/plog/hello-world",
            text="Hi",
            headers={"X-Cache": "unknown"},
        )
        response = admin_client.get(url, {"url": "hello-world"})
        assert response.status_code == 200
        data = response.json()
        assert data["absolute_url"] == "http://peterbecom.local/plog/hello-world"
        assert data["http_1"]["headers"]["X-Cache"] == "unknown"
        assert data["http_1"]["status_code"] == 200
        assert data["http_1"]["took"]
        assert data["http_1"]["x_cache"] == "unknown"


def test_cdn_purge(admin_client):
    url = reverse("api:cdn_purge")
    response = admin_client.post(url, {"urls": ["http://bla"]})
    assert response.status_code == 400
    response = admin_client.post(url, {"urls": ["blabla"]})
    assert response.status_code == 400
    response = admin_client.post(url, {"urls": ["/blabla"]})
    assert response.status_code == 200

    url = reverse("api:cdn_purge_urls")
    response = admin_client.get(url)
    assert response.status_code == 200

    data = response.json()
    assert not data["recent"]
    assert data["queued"]
