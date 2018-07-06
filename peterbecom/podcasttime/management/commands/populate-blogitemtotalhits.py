import time

from django.db.models import Count

from peterbecom.base.basecommand import BaseCommand
from peterbecom.plog.models import BlogItemTotalHits, BlogItemHit


class Command(BaseCommand):
    def _handle(self, *args, **kwargs):
        qs = BlogItemHit.objects.all()
        t0 = time.time()
        count_records = 0
        for aggregate in qs.values("blogitem_id").annotate(count=Count("blogitem_id")):
            hits, _ = BlogItemTotalHits.objects.get_or_create(
                blogitem_id=aggregate["blogitem_id"]
            )
            hits.total_hits = aggregate["count"]
            hits.save()
            count_records += 1
        t1 = time.time()

        self.notice(
            "Took {:.2f}s to update total hits for {} blogs".format(
                t1 - t0, count_records
            )
        )
