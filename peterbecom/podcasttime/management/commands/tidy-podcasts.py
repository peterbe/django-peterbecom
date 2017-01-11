from django.db.models import Max

from peterbecom.base.basecommand import BaseCommand
from peterbecom.podcasttime.models import Podcast, Episode


class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        podcasts = Podcast.objects.filter(name='')
        self.out(podcasts.count(), 'podcasts without a name')
        for podcast in podcasts:
            podcast.delete()

        podcasts = Podcast.objects.filter(latest_episode__isnull=True)
        self.out(podcasts.count(), 'podcasts without latest_episode')
        for podcast in podcasts.order_by('?')[:1000]:
            latest = Episode.objects.filter(podcast=podcast).aggregate(
                published=Max('published')
            )['published']
            if latest:
                print('PODCAST', repr(podcast), latest)
                podcast.latest_episode = latest
                podcast.save()
