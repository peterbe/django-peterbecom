from django.conf import settings
from django.core.management import CommandError

from peterbecom.base.basecommand import BaseCommand
from peterbecom.base.fscache import (
    find_missing_compressions,
    invalidate_too_old,
    purge_outdated_cdn_urls,
    clean_disfunctional_folders,
)
from peterbecom.base.cdn import keycdn_zone_check


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Print instead of deleting",
        )
        parser.add_argument(
            "--skip-cdn-purge",
            action="store_true",
            default=False,
            help="Don't bother executing CDN purge commands",
        )
        parser.add_argument(
            "--revisit",
            action="store_true",
            default=False,
            help="Try to request the original URL again",
        )
        parser.add_argument(
            "--max-files", default=100, help="Max number of URLs to purge (possibly)"
        )

    def handle(self, **options):
        if settings.DB_MAINTENANCE_MODE:
            print("DB maintenance mode")
            return

        invalidate_too_old(
            verbose=options["verbosity"] > 1,
            dry_run=options["dry_run"],
            revisit=options["revisit"],
        )

        find_missing_compressions(
            verbose=options["verbosity"] > 1,
            revisit=options["revisit"],
        )

        clean_disfunctional_folders(
            verbose=options["verbosity"] > 1,
            revisit=options["revisit"],
        )

        if not options["skip_cdn_purge"]:
            if not keycdn_zone_check():
                raise CommandError("KeyCDN Zone Check failed!")
            purge_outdated_cdn_urls(
                verbose=options["verbosity"] > 1,
                revisit=options["revisit"],
                dry_run=options["dry_run"],
                max_files=int(options["max_files"]),
            )
