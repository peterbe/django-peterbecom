from peterbecom.base.basecommand import BaseCommand
from peterbecom.podcasttime.models import Podcast
from peterbecom.podcasttime.scraper import download_episodes


class Command(BaseCommand):

    def _handle(self, *args, **kwargs):
        podcasts = Podcast.objects.filter(error__isnull=False)
        self.out(podcasts.count(), 'podcasts with errors')

        for podcast in podcasts.order_by('?')[:10]:
            print((podcast.name, podcast.id))
            print("ERROR (before)", repr(podcast.error[:100]))
            download_episodes(podcast, timeout=20)
            podcast.refresh_from_db()
            print("ERROR (after)", bool(podcast.error))
            print()
