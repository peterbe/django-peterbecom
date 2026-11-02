import pytest

from peterbecom.chiveproxy.models import Card, Picture


def _create_card():
    card = Card.objects.create(url="http://example.com", text="Bla bla", data={})
    card.data = {
        "img": "http://example.com/image.jpg",
        "uri": str(card.id),
        "date": card.created.strftime("%Y-%m-%d"),
        "text": "Example card",
    }
    card.save()
    return card


@pytest.mark.django_db
def test_set_image_proxy_conversions(settings):
    card = _create_card()
    picture = Picture.objects.create(
        card=card,
        img="https://example.com/image.jpg",
        gifsrc=None,
        mp4src=None,
        caption="Bla\nbla\n",
        caption_html="Bla<br>bla<br>",
        order_index=0,
    )
    assert picture.image_proxy_conversions
    img = picture.image_proxy_conversions["img"]
    assert img
    image_proxy_file_path = settings.IMAGE_PROXY_CACHE_ROOT / img
    assert not image_proxy_file_path.exists()
