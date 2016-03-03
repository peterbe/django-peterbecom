from celery.task import task

from peterbecom.apps.podcasttime.models import Podcast, PodcastError
from peterbecom.apps.podcasttime.scraper import (
    download_episodes,
    itunes_search,
)


@task()
def download_episodes_task(podcast_id, verbose=True):
    podcast = Podcast.objects.get(id=podcast_id)
    download_episodes(podcast, verbose=verbose)


@task()
def redownload_podcast_image(podcast_id):
    podcast = Podcast.objects.get(id=podcast_id)
    print "REDOWNLOAD_PODCAST_IMAGE!!"
    try:
        podcast.download_image()
        print "Worked!"
    except Exception:
        print "Failed!"
        PodcastError.create(podcast)
        raise


@task()
def fetch_itunes_lookup(podcast_id):
    podcast = Podcast.objects.get(id=podcast_id)
    results = itunes_search(podcast)
    if results['resultCount'] == 1:
        lookup = results['results'][0]
        podcast.itunes_lookup = lookup
        podcast.save()
