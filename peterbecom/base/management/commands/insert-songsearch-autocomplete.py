from peterbecom.base.basecommand import BaseCommand
from peterbecom.base.songsearch_autocomplete import insert


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Print instead of deleting",
        )
        parser.add_argument(
            "--impatient",
            action="store_true",
            default=False,
            help="Exit on errors immediately",
        )
        parser.add_argument("--page", default=1, help="Which page")

    def _handle(self, **options):
        dry_run = options["dry_run"]
        impatient = options["impatient"]
        page = int(options["page"])
        insert(dry_run=dry_run, impatient=impatient, page=page)
