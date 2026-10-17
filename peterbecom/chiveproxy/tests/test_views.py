import pytest
from django.urls import reverse

from peterbecom.chiveproxy.models import Card


@pytest.mark.django_db
def test_cards_empty(client):
    url = reverse("chiveproxy:api_cards")
    response = client.get(url)
    assert response.status_code == 200
    assert "cards" in response.json()
    assert response.json()["cards"] == []


def _create_card():
    card = Card.objects.create(url="http://example.com", text="Bla bla", data={})
    card.data = {
        "text": "Example card",
        "img": "http://example.com/image.jpg",
        "pictures": [
            {
                "img": "https://example.com/yourself-lead.png",
                "uri": str(card.id),
                "date": card.created.strftime("%Y-%m-%d"),
                "text": "Example card",
                "pictures": [
                    {
                        "img": "https://example.com/image.jpg",
                        "gifsrc": None,
                        "mp4src": None,
                        "caption": "Bla\nbla\n",
                        "caption_html": "Bla<br>bla<br>",
                    },
                ],
            }
        ],
    }
    card.save()
    return card


@pytest.mark.django_db
def test_cards_happy_path(client):
    card = _create_card()

    url = reverse("chiveproxy:api_cards")
    response = client.get(url)
    assert response.status_code == 200
    cards = response.json()["cards"]
    assert cards[0]["count_pictures"] == 1
    assert cards[0]["id"] == card.id
    assert cards[0]["img"] == "http://example.com/image.jpg"
    assert cards[0]["uri"] == card.id
    assert cards[0]["url"] == "http://example.com"


@pytest.mark.django_db
def test_card_happy_path(client):
    card = _create_card()

    url = reverse("chiveproxy:api_card", args=[card.id])
    response = client.get(url)
    assert response.status_code == 200

    card_json = response.json()

    assert card_json["date"]
    assert card_json["id"] == card.id
    assert card_json["text"] == "Example card"
    assert card_json["pictures"] == card.data["pictures"]


@pytest.mark.django_db
def test_card_brotli_compressed(client):
    card = _create_card()
    for i in range(15):
        card.data["pictures"][0]["pictures"].append(
            {
                "img": f"https://example.com/image{i}.jpg",
                "gifsrc": None,
                "mp4src": None,
                "caption": "it gets dark at like 3 PM in the winter.",
                "caption_html": "Bla<br>bla<br>",
            },
        )
    card.save()

    url = reverse("chiveproxy:api_card", args=[card.id])
    response = client.get(url, HTTP_ACCEPT_ENCODING="br")
    assert response.status_code == 200
    assert response.headers.get("Content-Encoding") == "br"

    url = reverse("chiveproxy:api_card", args=[card.id])
    response = client.get(url, HTTP_ACCEPT_ENCODING="zstd")
    assert response.status_code == 200
    assert response.headers.get("Content-Encoding") == "zstd"
