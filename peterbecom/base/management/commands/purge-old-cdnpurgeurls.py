import datetime

from django.utils import timezone
from peterbecom.base.basecommand import BaseCommand

from peterbecom.base.models import CDNPurgeURL


class Command(BaseCommand):
    def handle(self, **options):
        old = timezone.now() - datetime.timedelta(days=90)
        ancient = CDNPurgeURL.objects.filter(created__lt=old)
        print("{:,} ANCIENT CDNPurgeURLs".format(ancient.count()))
        ancient.delete()
