import time

import pytest
from django.urls import reverse
from django.utils import timezone

from peterbecom.plog.models import BlogItem, Category


@pytest.mark.django_db
def test_autocompete_search_empty(client):
    url = reverse("publicapi:autocompete")
    response = client.get(url)
    assert response.status_code == 400
    response = client.get(url, {"q": "fxx"})
    assert response.status_code == 200
    data = response.json()
    assert data["terms"] == ["fxx"]
    assert data["results"] == []


@pytest.mark.django_db
def test_search_empty(client):
    url = reverse("publicapi:search")
    response = client.get(url)
    assert response.status_code == 400
    response = client.get(url, {"q": "bla bla bla"})
    assert response.status_code == 200
    data = response.json()
    assert data["q"] == "bla bla bla"
    assert data["original_q"] == "bla bla bla"
    assert data["results"]["count_documents"] == 0
    assert data["results"]["count_documents_shown"] == 0
    assert data["results"]["documents"] == []
    assert data["results"]["search_time"] > 0


@pytest.mark.django_db
def test_search_happy_path(client):
    blogitem = BlogItem.objects.create(
        oid="hello-world",
        title="Hello World",
        pub_date=timezone.now(),
        proper_keywords=["one", "two"],
        display_format="markdown",
        text="Hello *world*\n<!--split-->Second part",
    )
    category = Category.objects.create(name="Code")
    blogitem.categories.add(category)
    blogitem.save()
    time.sleep(1)
    url = reverse("publicapi:search")
    response = client.get(url, {"q": "hello "})
    assert response.status_code == 200
    data = response.json()
    assert data["q"] == "hello"
    assert data["results"]["count_documents"] > 0


@pytest.mark.django_db
def test_autocomplete_empty(client):
    url = reverse("publicapi:autocomplete")
    response = client.get(url)
    assert response.status_code == 400
    response = client.get(url, {"q": "blablabl"})
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["found"] == 0
    assert data["results"] == []


@pytest.mark.django_db
def test_typeahead_happy_path(client):
    url = reverse("publicapi:typeahead")
    response = client.get(url, {"q": "p"})
    assert response.status_code == 200
    assert "public" in response.headers["cache-control"]
    data = response.json()
    assert data["meta"]["found"] > 0
    assert data["meta"]["took"]
    assert data["results"]
    assert data["results"][0]["highlights"]
    assert data["results"][0]["term"]


@pytest.mark.django_db
def test_typeahead_multiword(client):
    url = reverse("publicapi:typeahead")
    response = client.get(url, {"q": "peter s"})
    assert response.status_code == 200
    data = response.json()
    assert "public" in response.headers["cache-control"]
    assert data["meta"]["found"] > 0
    assert data["meta"]["took"]
    assert data["results"]
    assert data["results"][0]["highlights"]
    assert data["results"][0]["term"]


@pytest.mark.django_db
def test_typeahead_failing(client):
    url = reverse("publicapi:typeahead")
    response = client.get(url)
    assert response.status_code == 400
    response = client.get(url, {"q": "x" * 100})
    assert response.status_code == 400
    response = client.get(url, {"q": "x", "n": "100"})
    assert response.status_code == 400
    response = client.get(url, {"q": "x", "n": "xx"})
    assert response.status_code == 400
