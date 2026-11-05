from peterbecom.chiveproxy.models import Card


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
