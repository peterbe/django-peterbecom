from __future__ import absolute_import, unicode_literals
from celery import shared_task

from peterbecom.base.templatetags.jinja_helpers import thumbnail
from peterbecom.podcasttime.models import Podcast, PodcastError
from peterbecom.podcasttime.utils import get_podcast_metadata, NotFound
from peterbecom.podcasttime.scraper import (
    download_episodes,
    itunes_search,
)


@shared_task
def download_episodes_task(podcast_id, verbose=True):
    try:
        podcast = Podcast.objects.get(id=podcast_id)
    except Podcast.DoesNotExist:
        print("Warning! Podcast with id {} does not exist".format(
            podcast_id
        ))
        return
    try:
        download_episodes(podcast, verbose=verbose)
    except NotFound as exception:
        PodcastError.create(podcast)
        if isinstance(exception, bytes):
            podcast.error = exception.decode('utf-8')
        else:
            podcast.error = str(exception)
        podcast.save()


@shared_task
def redownload_podcast_image(podcast_id):
    podcast = Podcast.objects.get(id=podcast_id)
    print("REDOWNLOAD_PODCAST_IMAGE!!")
    try:
        podcast.download_image()
        # If it worked, it should be possible to make a thumbnail out of
        # if. I've seen downloaded images with the right content-type,
        # and with a size but when you try to turn it into a thumbnail
        # PIL throws IOErrors.
        assert podcast.image
        try:
            thumbnail(podcast.image, '300x300')
            print("Worked!")
        except IOError:
            print("Not a valid image if thumbnails can't be made")
            podcast.image = None
            podcast.save()
    except Exception:
        print("Failed!")
        PodcastError.create(podcast)
        raise


@shared_task
def fetch_itunes_lookup(podcast_id):
    podcast = Podcast.objects.get(id=podcast_id)
    print("Fetching itunes lookup", repr(podcast.name))
    results = itunes_search(podcast.name)
    if results['resultCount'] == 1:
        lookup = results['results'][0]
        podcast.itunes_lookup = lookup
        podcast.save()
    else:
        print("Found", results['resultCount'], 'results')
        print(results['resultCount'])


@shared_task
def download_podcast_metadata(podcast_id):
    metadata = get_podcast_metadata(
        Podcast.objects.get(id=podcast_id).url
    )
    if metadata:
        podcast = Podcast.objects.get(id=podcast_id)
        if metadata.get('link'):
            podcast.link = metadata['link']
        if metadata.get('subtitle'):
            podcast.subtitle = metadata['subtitle']
        if metadata.get('summary'):
            podcast.summary = metadata['summary']
        podcast.save()
