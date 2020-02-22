import datetime

from django.utils import timezone

from peterbecom.base.models import CommandRun
from peterbecom.base.basecommand import BaseCommand


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--days", default=90)

    def _handle(self, **options):
        days = int(options["days"])

        old = timezone.now() - datetime.timedelta(days=days)
        runs = CommandRun.objects.filter(created__lt=old)
        count, _ = runs.delete()
        self.out("Deleted {} old command runs".format(count))
