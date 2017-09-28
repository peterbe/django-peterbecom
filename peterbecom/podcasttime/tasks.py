from __future__ import absolute_import, unicode_literals
from celery import shared_task
from requests.exceptions import ReadTimeout, ConnectTimeout

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
    print("Fetching itunes lookup: {!r}".format(podcast.name))
    results = itunes_search(podcast.name)
    if not results:
        print('Nothing returned on itunes lookup: {!r}'.format(podcast.name))
        return
    if results['resultCount'] == 1:
        lookup = results['results'][0]
        podcast.itunes_lookup = lookup
        podcast.save()
    elif results['resultCount'] > 1:
        # Pick the first one if it's a slam dunk
        lookup = results['results'][0]
        if podcast.name.lower() == lookup['collectionName'].lower():
            podcast.itunes_lookup = lookup
            podcast.save()
        elif podcast.url in [x.get('feedUrl') for x in results['results']]:
            lookup = [
                x for x in results['results']
                if x['feedUrl'] == podcast.url
            ][0]
            podcast.itunes_lookup = lookup
            podcast.save()
        else:
            print("Too ambiguous ({!r} != {!r}, {!r} != {!r})".format(
                podcast.name, lookup['collectionName'],
                podcast.url, lookup['feedUrl'],
            ))
    else:
        print("Found no results")


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


@shared_task
def search_by_itunes(q):
    try:
        print("ITUNES SEARCHING {!r}".format(q))
        results = itunes_search(
            q,
            attribute='titleTerm',
            timeout=6,
        )['results']
    except (ReadTimeout, ConnectTimeout):
        results = []
    print("FOUND {}".format(len(results)))

    count_new = 0
    for result in results[:10]:
        try:
            podcast = Podcast.objects.get(
                url=result['feedUrl'],
                name=result['collectionName']
            )
        except Podcast.DoesNotExist:
            assert result['collectionName'], result
            podcast = Podcast.objects.create(
                name=result['collectionName'],
                url=result['feedUrl'],
                itunes_lookup=result,
                image_url=result['artworkUrl600'],
            )
            try:
                podcast.download_image(timeout=3)
            except (ReadTimeout, ConnectTimeout):
                redownload_podcast_image(podcast.id)
            download_episodes_task.delay(podcast.id)
            count_new += 1

    print('Found {} new podcasts by iTunes search'.format(count_new))
