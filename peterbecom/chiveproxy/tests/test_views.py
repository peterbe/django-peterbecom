import pytest
from django.urls import reverse

from peterbecom.chiveproxy.models import Card, Picture


@pytest.mark.django_db
def test_cards_empty(client):
    url = reverse("chiveproxy:api_cards")
    response = client.get(url)
    assert response.status_code == 200
    assert "cards" in response.json()
    assert response.json()["cards"] == []


def _create_card_legacy_style():
    card = Card.objects.create(url="http://example.com", text="Bla bla", data={})
    card.data = {
        "img": "http://example.com/image.jpg",
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
    card.save()
    return card


def _create_card(create_picture=True):
    card = Card.objects.create(url="http://example.com", text="Bla bla", data={})
    card.data = {
        "img": "http://example.com/image.jpg",
        "uri": str(card.id),
        "date": card.created.strftime("%Y-%m-%d"),
        "text": "Example card",
    }
    card.save()
    if create_picture:
        Picture.objects.create(
            card=card,
            img="https://example.com/image.jpg",
            gifsrc=None,
            mp4src=None,
            caption="Bla\nbla\n",
            caption_html="Bla<br>bla<br>",
            order_index=0,
        )

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
    pictures = Picture.objects.filter(card=card).order_by("order_index")
    first_picture = pictures[0]
    assert card_json["pictures"][0] == {
        "img": first_picture.img,
        "gifsrc": first_picture.gifsrc or None,
        "mp4src": first_picture.mp4src or None,
        "caption": first_picture.caption,
        "caption_html": first_picture.caption_html,
    }


@pytest.mark.django_db
def test_cards_legacy(client):
    card = _create_card_legacy_style()

    url = reverse("chiveproxy:api_cards")
    response = client.get(url)
    assert response.status_code == 200
    cards = response.json()["cards"]
    print("CARDS:", cards)
    assert cards[0]["count_pictures"] == 1
    assert cards[0]["id"] == card.id
    assert cards[0]["img"] == "http://example.com/image.jpg"
    assert cards[0]["uri"] == card.id
    assert cards[0]["url"] == "http://example.com"


@pytest.mark.django_db
def test_card_legacy(client):
    card = _create_card_legacy_style()

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
    card = _create_card(create_picture=False)

    bulk = []
    for i in range(15):
        bulk.append(
            Picture(
                card=card,
                img=f"https://example.com/image{i}.jpg",
                gifsrc="",
                mp4src="",
                caption="it gets dark at like 3 PM in the winter.",
                caption_html="Bla<br>bla<br>",
                order_index=i,
            )
        )
    Picture.objects.bulk_create(bulk)

    url = reverse("chiveproxy:api_card", args=[card.id])
    response = client.get(url, HTTP_ACCEPT_ENCODING="br")
    assert response.status_code == 200
    assert response.headers.get("Content-Encoding") == "br"

    url = reverse("chiveproxy:api_card", args=[card.id])
    response = client.get(url, HTTP_ACCEPT_ENCODING="zstd")
    assert response.status_code == 200
    assert response.headers.get("Content-Encoding") == "zstd"
