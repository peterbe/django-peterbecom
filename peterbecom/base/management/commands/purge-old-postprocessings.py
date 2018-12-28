import datetime

from django.utils import timezone
from peterbecom.base.basecommand import BaseCommand

from peterbecom.base.models import PostProcessing


class Command(BaseCommand):
    # def add_arguments(self, parser):
    #     parser.add_argument(
    #         "--dry-run",
    #         action="store_true",
    #         default=False,
    #         help="Print instead of deleting",
    #     )

    def handle(self, **options):
        old = timezone.now() - datetime.timedelta(days=90)
        ancient = PostProcessing.objects.filter(created__lt=old)
        print("ANCIENT", ancient.delete())

        old = timezone.now() - datetime.timedelta(hours=1)
        stuck = PostProcessing.objects.filter(
            duration__isnull=True, exception__isnull=True, created__lt=old
        )
        print("STUCK", stuck.delete())
