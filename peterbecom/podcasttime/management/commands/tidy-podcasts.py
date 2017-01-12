import datetime

from django.db.models import F
from django.utils import timezone

from peterbecom.base.basecommand import BaseCommand
from peterbecom.podcasttime.models import Podcast, Picked


class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        podcasts = Podcast.objects.filter(name='')
        self.out(podcasts.count(), 'podcasts without a name')
        for podcast in podcasts:
            podcast.delete()

        podcasts = Podcast.objects.filter(latest_episode__isnull=True)
        self.out(podcasts.count(), 'podcasts without latest_episode')
        for podcast in podcasts.order_by('?')[:1000]:
            if podcast.update_latest_episode():
                print('PODCAST', repr(podcast), podcast.latest_episode)

        podcasts = Podcast.objects.filter(
            latest_episode__isnull=False,
            last_fetch__isnull=False,
            last_fetch__gt=F('latest_episode')
        )
        for podcast in podcasts.order_by('?')[:10]:
            if podcast.update_latest_episode():
                print('PODCAST', repr(podcast), podcast.latest_episode)

        yesterday = timezone.now() - datetime.timedelta(days=1)
        picks = Picked.objects.filter(created__lt=yesterday)
        deleted_picks = 0
        for pick in picks.order_by('created'):
            if pick.podcasts.all().count() <= 1:
                pick.delete()
                deleted_picks += 1
        if deleted_picks:
            self.out(deleted_picks, 'deleted because they only had 1 podcast')
