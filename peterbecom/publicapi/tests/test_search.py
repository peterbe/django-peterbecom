import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_autocompete_search_empty(client):
    url = reverse("publicapi:autocompete")
    response = client.get(url)
    assert response.status_code == 400
    response = client.get(url, {"q": "foo"})
    assert response.status_code == 200
    data = response.json()
    assert data["terms"] == ["foo"]
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
def test_autocomplete_empty(client):
    url = reverse("publicapi:autocomplete")
    response = client.get(url)
    assert response.status_code == 400
    response = client.get(url, {"q": "blablabl"})
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["found"] == 0
    assert data["results"] == []
