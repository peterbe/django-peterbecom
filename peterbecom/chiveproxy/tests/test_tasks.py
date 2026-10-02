import pytest

from peterbecom.chiveproxy.models import Card
from peterbecom.chiveproxy.tasks import remove_banned_pictures


@pytest.mark.django_db
def test_remove_banned_pictures():
    data = {
        "img": "https://example.com/Refuse2Delete.png?attachment_cache_bust=5310465&w=600",
        "uri": "9884c7ac",
        "date": "2026-10-1",
        "text": "Bla bla bla",
        "pictures": [
            {
                "img": "https://example.com/2/Hana-Good-One-GIF-45.jpg",
                "gifsrc": None,
                "mp4src": "https://example.com/2/Thisisalsobanned.mp4?attachment_cache_bust=5310402",
                "caption": "Bla bla",
                "caption_html": "bla<br>bla",
            },
            {
                "img": "https://example.com/2/random-memes-refuse-to-delete-part-35-.png?attachment_cache_bust=5310451&w=650",
                "gifsrc": None,
                "mp4src": None,
                "caption": "",
                "caption_html": "",
            },
        ],
        "human_time": "10 hours ago",
    }
    card1 = Card.objects.create(url="http://example.com/1", data=data)

    data = {
        "img": "https://example.com/2",
        "uri": "xxx111",
        "date": "2026-10-1",
        "text": "Bla bla bla",
        "pictures": [
            {
                "img": "https://example.com/2/Hana-Good-One-GIF-45.jpg",
                "gifsrc": None,
                "mp4src": "https://example.com/2/Hana-Good-One-GIF.mp4?attachment_cache_bust=5310402",
                "caption": "Bla bla",
                "caption_html": "bla<br>bla",
            },
            {
                "img": "https://example.com/2/this-is-banned.png?attachment_cache_bust=5310451&w=650",
                "gifsrc": None,
                "mp4src": None,
                "caption": "",
                "caption_html": "",
            },
        ],
        "human_time": "10 hours ago",
    }
    card2 = Card.objects.create(url="http://example.com/2", data=data)
    remove_banned_pictures()

    card1.refresh_from_db()
    assert len(card1.data["pictures"]) == 1
    card2.refresh_from_db()
    assert len(card2.data["pictures"]) == 1
