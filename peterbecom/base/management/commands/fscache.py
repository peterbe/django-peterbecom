from peterbecom.base.basecommand import BaseCommand

from peterbecom.base.fscache import invalidate_too_old


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Print instead of deleting",
        )
        parser.add_argument(
            "--revisit",
            action="store_true",
            default=False,
            help="Try to request the original URL again",
        )

    def handle(self, **options):
        # Might want to do more here
        invalidate_too_old(
            verbose=options["verbosity"] > 1,
            dry_run=options["dry_run"],
            revisit=options["revisit"],
        )
