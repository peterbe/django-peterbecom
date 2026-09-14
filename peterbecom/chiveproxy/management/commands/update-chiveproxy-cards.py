from django.core.management.base import BaseCommand

from peterbecom.chiveproxy.models import Card
from peterbecom.chiveproxy.views import update_cards


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--limit", default=100)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, **options):
        limit = int(options["limit"])
        dry_run = options["dry_run"]
        print(
            "Warning! This is run by a huey periodic task regularly already. "
            "Use the periodic task instead!"
        )
        try:
            update_cards(limit=limit, debug=True, dry_run=dry_run)
        except Exception:
            import sys
            import traceback

            print(" **** WARNING **** ")
            etype, evalue, tb = sys.exc_info()
            traceback.print_tb(tb)
            print("type:", etype)
            print("value:", evalue)
            print()
            raise

        if dry_run:
            print("Dry run mode, not making any changes.")
            return

        previous = None
        qs = Card.objects.all().order_by("-created")

        for c in qs[:10]:
            if c.data["text"] == previous:
                print("DELETE", c.id, c.data["text"])
                c.delete()
            # else:
            #     print("KEEP", c.id, c.data["text"])
            previous = c.data["text"]
