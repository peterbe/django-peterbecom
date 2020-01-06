from peterbecom.base.basecommand import BaseCommand
from peterbecom.plog.popularity import update_all


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--limit", default=2000)
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Don't actually approve the good candidates",
        )
        parser.add_argument(
            "--reindex",
            action="store_true",
            default=False,
            help="Reindex in Elasticsearch",
        )

    def _handle(self, **options):
        limit = int(options["limit"])
        verbose = int(options["verbosity"]) >= 2
        dry_run = options["dry_run"]
        reindex = options["reindex"]

        ids = update_all(verbose=verbose, dry_run=dry_run, limit=limit, reindex=reindex)
        self.out(
            "Recalculated {} {:,} IDs".format(
                reindex and "and reindexed" or "", len(ids)
            )
        )
