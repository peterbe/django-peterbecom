from django.conf import settings
from django.core.management.base import BaseCommand

from peterbecom.plog.popularity import update_all


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--limit", default=2000)
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Don't actually save or do anything persistent",
        )
        parser.add_argument(
            "--reindex",
            action="store_true",
            default=False,
            help="Reindex",
        )

    def handle(self, **options):
        if settings.DB_MAINTENANCE_MODE:
            print("DB maintenance mode")
            return
        limit = int(options["limit"])
        verbose = int(options["verbosity"]) >= 2
        dry_run = options["dry_run"]
        reindex = options["reindex"]

        ids = update_all(verbose=verbose, dry_run=dry_run, limit=limit, reindex=reindex)
        self.stdout.write(
            "Recalculated {} {:,} IDs".format(
                reindex and "and reindexed" or "", len(ids)
            )
        )
