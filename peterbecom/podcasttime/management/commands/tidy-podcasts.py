from django.db.models import F

from peterbecom.base.basecommand import BaseCommand
from peterbecom.podcasttime.models import Podcast


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
