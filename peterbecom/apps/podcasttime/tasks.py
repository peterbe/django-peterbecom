from celery.task import task

from peterbecom.apps.podcasttime.models import Podcast
from peterbecom.apps.podcasttime.scraper import download_episodes


@task()
def download_episodes_task(podcast_id, verbose=True):
    podcast = Podcast.objects.get(id=podcast_id)
    download_episodes(podcast, verbose=verbose)


@task()
def redownload_podcast_image(podcast_id):
    podcast = Podcast.objects.get(id=podcast_id)
    podcast.download_image()
