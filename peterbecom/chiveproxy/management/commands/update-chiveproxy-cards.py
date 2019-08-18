from peterbecom.base.basecommand import BaseCommand
from peterbecom.chiveproxy.views import update_cards


class Command(BaseCommand):
    def handle(self, **options):
        print(
            "Warning! This is run by a huey periodic task regularly already. "
            "Use the periodic task instead!"
        )
        update_cards()
