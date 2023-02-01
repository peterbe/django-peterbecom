import time

from peterbecom.base.basecommand import BaseCommand
from peterbecom.plog.models import BlogItemTotalHits


class Command(BaseCommand):
    def _handle(self, *args, **kwargs):
        t0 = time.time()
        count_records = BlogItemTotalHits.update_all()
        t1 = time.time()

        self.notice(
            "Took {:.2f}s to update total hits for {} blogs".format(
                t1 - t0, count_records
            )
        )
