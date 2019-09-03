import datetime

from django.utils import timezone
from peterbecom.base.basecommand import BaseCommand

from peterbecom.base.models import PostProcessing


class Command(BaseCommand):
    def handle(self, **options):
        print(
            "Use the periodic task in "
            "peterbecom.base.tasks.purge_old_postprocessings instead!!!"
        )
        old = timezone.now() - datetime.timedelta(days=90)
        ancient = PostProcessing.objects.filter(created__lt=old)
        print("{:,} ANCIENT PostProcessings".format(ancient.count()))
        ancient.delete()

        old = timezone.now() - datetime.timedelta(hours=1)
        stuck = PostProcessing.objects.filter(
            duration__isnull=True, exception__isnull=True, created__lt=old
        )
        if stuck.exists():
            print("{} STUCK PostProcessings".format(stuck.count()))
            stuck.delete()
