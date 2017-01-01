import datetime

from django.db.models import Count
from django.utils import timezone

from peterbecom.base.basecommand import BaseCommand
from peterbecom.podcasttime.scraper import download_some_episodes
from peterbecom.podcasttime.models import Podcast


class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        max_ = 5
        verbose = int(kwargs['verbosity']) >= 2
        self.print_stats('BEFORE')
        download_some_episodes(max_=max_, verbose=verbose)
        self.print_stats('AFTER')

    def print_stats(self, prefix):
        podcasts_wo_episodes = Podcast.objects.all().annotate(
            subcount=Count('episode')
        ).filter(subcount=0)
        self.out(prefix, podcasts_wo_episodes.count(), 'without episodes')

        podcasts_w_null_last_fetch = Podcast.objects.filter(
            last_fetch__isnull=True
        )
        self.out(
            prefix,
            podcasts_w_null_last_fetch.count(),
            'with no last_fetch'
        )

        last_week = timezone.now() - datetime.timedelta(days=7)
        podcasts_w_old_last_fetch = Podcast.objects.filter(
            last_fetch__isnull=False,
            last_fetch__lt=last_week,
        )
        self.out(
            prefix,
            podcasts_w_old_last_fetch.count(),
            'with last_fetch older than last week'
        )
