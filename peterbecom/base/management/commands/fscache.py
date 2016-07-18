from django.core.management.base import BaseCommand

from peterbecom.base.fscache import invalidate_too_old


class Command(BaseCommand):

    def handle(self, **options):
        # Might want to do more here
        invalidate_too_old(verbose=options['verbosity'] >= 1)
