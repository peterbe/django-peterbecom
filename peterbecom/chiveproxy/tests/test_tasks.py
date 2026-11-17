import pytest

from peterbecom.chiveproxy.models import BannedUrlPattern, Card, Picture
from peterbecom.chiveproxy.tasks import remove_banned_pictures


@pytest.mark.django_db
def test_remove_banned_pictures():
    data = {
        "img": "https://example.com/Refuse2Delete.png?attachment_cache_bust=5310465&w=600",
        "uri": "9884c7ac",
        "date": "2026-10-1",
    }
    card1 = Card.objects.create(
        url="http://example.com/1", data=data, text="Bla bla bla"
    )
    for p in [
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
    ]:
        Picture.objects.create(card=card1, **p)

    data = {
        "img": "https://example.com/2",
        "uri": "xxx111",
        "date": "2026-10-1",
    }
    card2 = Card.objects.create(
        url="http://example.com/2", text="Bla bla bla", data=data
    )
    for p in [
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
    ]:
        Picture.objects.create(card=card2, **p)

    pattern1 = BannedUrlPattern.objects.create(
        pattern="Thisisalsobanned.mp4",
        is_regex=False,
        case_insensitive=False,
    )
    pattern2 = BannedUrlPattern.objects.create(
        pattern="this-is-banned.png",
        is_regex=False,
        case_insensitive=False,
    )
    remove_banned_pictures()

    pattern1.refresh_from_db()
    assert pattern1.kills == 1
    pattern2.refresh_from_db()
    assert pattern2.kills == 1

    assert Picture.objects.filter(card=card1).count() == 1
    assert Picture.objects.filter(card=card2).count() == 1

    pattern3 = BannedUrlPattern.objects.create(
        pattern=r"Delete-part-\d+-\.png",
        is_regex=True,
        case_insensitive=True,
    )
    pattern4 = BannedUrlPattern.objects.create(
        pattern=r"(One|Two)-GIF.mp4",
        is_regex=True,
        case_insensitive=False,
    )
    remove_banned_pictures()

    assert Picture.objects.filter(card=card1).count() == 0
    assert Picture.objects.filter(card=card2).count() == 0

    pattern3.refresh_from_db()
    assert pattern3.kills == 1
    pattern4.refresh_from_db()
    assert pattern4.kills == 1
