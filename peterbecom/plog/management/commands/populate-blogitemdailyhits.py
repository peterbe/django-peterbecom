import datetime
import time

from django.core.management.base import BaseCommand
from django.db.models import Max, Min
from django.utils import timezone

from peterbecom.plog.models import BlogItemDailyHits, BlogItemDailyHitsExistingError


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("-d", "--days-back", default=1)
        parser.add_argument("-s", "--start-back", default=0)

    def handle(self, **options):
        if options["verbosity"] > 1:
            self._print_stats()
            print()

        date = timezone.now()
        one_day = datetime.timedelta(days=1)
        start_back = int(options["start_back"])
        date -= datetime.timedelta(days=start_back)
        for i in range(int(options["days_back"])):
            date -= one_day
            try:
                t0 = time.time()
                sum_, count = BlogItemDailyHits.rollup_date(date)
                t1 = time.time()
                self.stdout.write(
                    "Took {:.2f}s to update daily hits for {} "
                    "({:,} blogitems, sum total {:,} hits)".format(
                        t1 - t0, date.date(), count, sum_
                    )
                )
            except BlogItemDailyHitsExistingError:
                self.stdout.write("Daily hits for {} already done".format(date.date()))

        if options["verbosity"] > 1:
            print()
            self._print_stats()

    def _print_stats(self):
        oldest = BlogItemDailyHits.objects.aggregate(date=Min("date"))["date"]
        print("Oldest aggregate:", oldest)
        newest = BlogItemDailyHits.objects.aggregate(date=Max("date"))["date"]
        print("Newest aggregate:", newest)
