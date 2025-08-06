import time

from django.core.management.base import BaseCommand

from peterbecom.plog.models import BlogItemTotalHits


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        t0 = time.time()
        count_records = BlogItemTotalHits.update_all()
        t1 = time.time()

        self.stdout.write(
            "Took {:.2f}s to update total hits for {} blogs".format(
                t1 - t0, count_records
            )
        )
