from peterbecom.base.basecommand import BaseCommand
from peterbecom.chiveproxy.views import update_cards
from peterbecom.chiveproxy.models import Card


class Command(BaseCommand):
    def handle(self, **options):
        print(
            "Warning! This is run by a huey periodic task regularly already. "
            "Use the periodic task instead!"
        )
        update_cards(debug=True)

        previous = None
        qs = Card.objects.all().order_by("-created")

        for c in qs[:10]:
            if c.data["text"] == previous:
                print("DELETE", c.id, c.data["text"])
                c.delete()
            # else:
            #     print("KEEP", c.id, c.data["text"])
            previous = c.data["text"]
