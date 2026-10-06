from django.core.management.base import BaseCommand

from peterbecom.chiveproxy.tasks import remove_banned_pictures


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--limit", default=10)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, **options):
        limit = int(options["limit"])
        print(
            "Warning! This is run by a huey periodic task regularly already. "
            "Use the periodic task instead!"
        )
        dry_run = options["dry_run"]
        remove_banned_pictures(limit=limit, dry_run=dry_run)
