from pprint import pprint

from django.core.management.base import BaseCommand, CommandError

from peterbecom.apps.nodomains.tasks import run_url


class Command(BaseCommand):

    help = 'http://example.com'

    def handle(self, *args, **options):
        if len(args) != 1:
            raise CommandError('Must provide exactly one URL')

        url, = args
        pprint(run_url(url, dry_run=True))
