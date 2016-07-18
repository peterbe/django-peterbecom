from django.core.management.base import BaseCommand

from peterbecom.base.fscache import invalidate_too_old


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            # dest='delete',
            default=False,
            help='Print instead of deleting'
        )

    def handle(self, **options):
        # Might want to do more here
        invalidate_too_old(
            verbose=options['verbosity'] >= 1,
            dry_run=options['dry_run'],
        )
