from celery.task import task

from peterbecom.apps.podcasttime.models import Podcast
from peterbecom.apps.podcasttime.scraper import download_episodes


@task()
def download_episodes_task(podcast_id, verbose=True):
    podcast = Podcast.objects.get(id=podcast_id)
    download_episodes(podcast, verbose=verbose)

print "download_episodes_task REGISTERED!!"
