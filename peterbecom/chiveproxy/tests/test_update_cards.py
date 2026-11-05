import hashlib

import pytest

from peterbecom.chiveproxy import update_cards as update_cards_module
from peterbecom.chiveproxy.models import Card, Picture
from peterbecom.chiveproxy.update_cards import update_cards


def _fake_get_cards(limit=None, debug=False, html=None):
    # count = 0
    for i in range(limit if limit is not None else 9):
        href = f"https://choive.com/2026/11/05/fake-card-{i}/"
        yield {
            "url": href,
            "uri": hashlib.md5(href.encode("utf-8")).hexdigest()[:8],
            "text": f"Fake card {i}",
            "img": f"https://choive.com/wp-content/uploads/fake-{i}.jpg",
            "date": f"2026-11-05T{i // 60:02d}:{i % 60:02d}:00+00:00",
        }
        # count += 1
        # if limit and count >= limit:
        #     break


@pytest.fixture
def mock_get_cards(monkeypatch):
    monkeypatch.setattr(update_cards_module, "get_cards", _fake_get_cards)


def _fake_get_card(url: str):
    return {
        "text": "Fake card",
        "pictures": [
            {
                "img": "https://choive.com/wp-content/uploads/fake-0.jpg",
                "gifsrc": None,
                "mp4src": None,
                "caption": "Fake caption",
                "caption_html": "<p>Fake caption</p>",
            }
        ],
        "date": "2026-11-05T00:00:00+00:00",
    }


@pytest.fixture
def mock_get_card(monkeypatch):
    monkeypatch.setattr(update_cards_module, "get_card", _fake_get_card)


@pytest.mark.django_db
def test_update_cards_happy_path(mock_get_cards, mock_get_card, requestsmock):
    with open("peterbecom/chiveproxy/tests/test_image.jpeg", "rb") as f:
        data = f.read()
        requestsmock.get(
            "https://chive.peterbe.com/api/imageproxy?url=https%3A%2F%2Fchoive.com%2Fwp-content%2Fuploads%2Ffake-0.jpg",
            content=data,
            headers={"content-length": str(len(data)), "content-type": "image/jpeg"},
        )
        requestsmock.get(
            "https://chive.peterbe.com/api/imageproxy?url=https%3A%2F%2Fchoive.com%2Fwp-content%2Fuploads%2Ffake-1.jpg",
            content=data,
            headers={"content-length": str(len(data)), "content-type": "image/jpeg"},
        )
    count_updated, count_tried = update_cards(limit=2)
    assert count_updated == 2
    assert count_tried == 2

    cards_created = Card.objects.all()
    assert cards_created.count() == 2
    pictures_created = Picture.objects.all()
    assert pictures_created.count() == 2

    assert requestsmock.call_count == 2
    first, second = requestsmock.request_history
    assert first.method == "GET"
    assert (
        first.url
        == "https://chive.peterbe.com/api/imageproxy?url=https%3A%2F%2Fchoive.com%2Fwp-content%2Fuploads%2Ffake-0.jpg"
    )
    assert second.method == "GET"
    assert (
        second.url
        == "https://chive.peterbe.com/api/imageproxy?url=https%3A%2F%2Fchoive.com%2Fwp-content%2Fuploads%2Ffake-0.jpg"
    )
