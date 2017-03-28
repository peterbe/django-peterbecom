import hashlib
import time
import datetime
import random
from urllib.parse import urljoin, urlparse
from xml.parsers.expat import ExpatError

import requests
from requests.exceptions import ConnectionError, ReadTimeout
import pyquery
import feedparser

from django.utils import timezone
from django.db.models import Count, Max
from django.db.utils import DataError
from django.utils.html import strip_tags
from django.conf import settings

from peterbecom.podcasttime.models import (
    Podcast,
    Episode,
    PodcastError,
    NotAnImageError,
)

from peterbecom.podcasttime.utils import (
    download,
    parse_duration_ffmpeg,
    get_image_url,
    get_base_url,
    NotFound,
    NotXMLResponse,
)


class BadPodcastEntry(Exception):
    pass


class BadEpisodeDurationError(Exception):
    """when an episode is so bad it doesn't have a valid duration"""


def itunes_lookup(itunes_id):
    url = 'https://itunes.apple.com/lookup'
    response = requests.get(url, {'id': itunes_id})
    return response.json()


def itunes_search(term, **options):
    timeout = options.pop('timeout', None)
    options.update({'term': term, 'entity': 'podcast'})
    url = 'https://itunes.apple.com/search'
    response = requests.get(url, options, timeout=timeout)
    return response.json()


def download_some_episodes(max_=5, verbose=False, timeout=10):
    # first attempt podcasts that have 0 episodes
    podcasts = Podcast.objects.filter(error__isnull=True).annotate(
        subcount=Count('episode')
    ).filter(subcount=0)

    for podcast in podcasts.order_by('?')[:max_]:
        if verbose:
            print(podcast.name, podcast.last_fetch)
        download_episodes(podcast, timeout=timeout)

    # secondly, do those whose episodes have never been fetched
    podcasts = Podcast.objects.filter(
        error__isnull=True,
        last_fetch__isnull=True
    ).order_by('?')
    for podcast in podcasts[:max_]:
        if verbose:
            print(podcast.name, podcast.last_fetch)
        download_episodes(podcast, timeout=timeout)

    # randomly do some of the old ones
    then = timezone.now() - datetime.timedelta(days=7)
    podcasts = Podcast.objects.filter(
        error__isnull=True,
        last_fetch__lt=then
    ).order_by('?')
    for podcast in podcasts[:max_]:
        if verbose:
            print(podcast.name, podcast.last_fetch)
        download_episodes(podcast, timeout=timeout)


def download_episodes(podcast, verbose=True, timeout=10):
    try:
        _download_episodes(podcast, verbose=verbose, timeout=timeout)
        if podcast.error:
            p = Podcast.objects.get(id=podcast.id)
            p.error = None
            p.save()
    except Podcast.DoesNotExist:
        raise
    except Exception as exception:
        if settings.DEBUG:
            raise
        try:
            p = Podcast.objects.get(id=podcast.id)
            if isinstance(exception, bytes):
                p.error = exception.decode('utf-8')
            else:
                p.error = str(exception)
            p.save()
        except Podcast.DoesNotExist:
            print('Podcast with ID {!r} does not exist'.format(podcast.id))


def _download_episodes(podcast, verbose=True, timeout=10):
    xml = download(podcast.url, timeout=timeout)
    d = feedparser.parse(xml)

    def get_duration(entry):
        if not entry.get('itunes_duration'):
            try:
                for link in entry['links']:
                    if (
                        link['type'] == 'audio/mpeg' or
                        link['href'].lower().endswith('.mp3')
                    ):
                        duration, error = parse_duration_ffmpeg(
                            link['href']
                        )
                        if error:
                            raise BadEpisodeDurationError(error)
                        return duration
            except KeyError:
                try:
                    print(entry.enclosure)
                    raise Exception(entry.enclosure)
                except AttributeError:
                    # no 'itunes:duration' and no links
                    print("SKIPPING", entry)
                    return
        elif entry['itunes_duration'].count(':') >= 1:
            try:
                itunes_duration = entry['itunes_duration']
                # a bug in bad podcasts
                itunes_duration = itunes_duration.replace('>', '')
                itunes_duration = itunes_duration.replace(';', '')

                itunes_duration = [
                    int(float(x)) for x in itunes_duration.split(':')
                    if x.strip()
                ]
            except ValueError:
                print("SKIPPING, BAD itunes_duration")
                print(entry)
                print('itunes_duration=', repr(entry['itunes_duration']))
                return
            duration = 0
            itunes_duration.reverse()
            duration += itunes_duration[0]  # seconds
            if len(itunes_duration) > 1:
                duration += 60 * itunes_duration[1]  # minutes
                if len(itunes_duration) > 2:
                    duration += 60 * 60 * itunes_duration[2]  # hours
            if duration > 24 * 60 * 60:
                entry['itunes_duration'] = None
                return get_duration(entry)
            return duration
        else:
            if not entry['itunes_duration']:
                print("BUT!", xml.find('<itunes:duration'))
                return
            try:
                return(int(float(entry['itunes_duration'])))
            except ValueError:
                # pprint(entry)
                print("SKIPPING itunes_duration not a number")
                print(repr(entry['itunes_duration']))
                return

    for entry in d['entries']:
        if not entry.get('published_parsed'):
            # print "Entry without a valid 'published_parsed'!"
            # print entry
            raise BadPodcastEntry(
                "Entry without a valid 'published_parsed'! ({})".format(
                    podcast.url
                )
            )

        published = datetime.datetime.fromtimestamp(
            time.mktime(entry['published_parsed'])
        )
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        duration = get_duration(entry)
        if duration is None:
            continue
        try:
            guid = entry.guid
        except AttributeError:
            try:
                guid = entry.id
            except AttributeError:
                print("No guid or id. Going to use the summary.")
                try:
                    guid = hashlib.md5(
                        entry.summary.encode('utf-8')
                    ).hexdigest()
                except AttributeError:
                    print(
                        "No guid or id or summary. ",
                        "Going to use the title."
                    )
                    guid = hashlib.md5(
                        entry.title.encode('utf-8')
                    ).hexdigest()
                # raise
        try:
            ep = Episode.objects.get(
                podcast=podcast,
                guid=guid
            )
            if ep.duration != duration:
                print("DURATION CHANGED!!!")
            else:
                print("Duration unchanged")
            if ep.published != published:
                print("PUBLISHED CHANGED!!!")
            else:
                print("Published unchanged")
        except Episode.DoesNotExist:
            pass

        metadata = dict(entry)
        title = strip_tags(metadata.get('title'))
        summary = strip_tags(metadata.get('summary'))

        try:
            episode = Episode.objects.get(
                podcast=podcast,
                guid=guid
            )
            episode.duration = duration
            episode.published = published
            episode.metadata = metadata
            episode.title = title
            episode.summary = summary

            try:
                episode.save()
                print("SAVED")
            except DataError:
                print("FROM", podcast.url)
                print("ENTRY")
                print(entry)
                print("TRIED TO SAVE DURATION", duration)
                PodcastError.create(podcast, notes='Tried to save duration')
                raise
        except Episode.DoesNotExist:
            episode = Episode.objects.create(
                podcast=podcast,
                duration=duration,
                published=published,
                guid=guid,
                metadata=metadata,
                title=title,
                summary=summary,
            )
            print("CREATED")
        print(
            episode.podcast.name,
            episode.guid,
            episode.duration,
            episode.published
        )
    print("SETTING last_fetch ON {!r}".format(podcast))
    latest_episode = Episode.objects.filter(podcast=podcast).aggregate(
        latest=Max('published')
    )['latest']
    print("SETTING latest_episode {!r}".format(latest_episode))
    podcast = Podcast.objects.get(id=podcast.id)
    podcast.last_fetch = timezone.now()
    podcast.latest_episode = latest_episode
    podcast.save()


def find_podcasts(url, verbose=False, depth=0):
    urls = []
    hash_ = hashlib.md5(
        get_base_url(url).encode('utf-8')
    ).hexdigest()
    print(url, hash_, depth)
    if hash_ == '73eb773086aa7f75654f4a2d25ca315b':
        if not depth:
            url = url + '/feeds'
        html = download(url)
        doc = pyquery.PyQuery(html)
        doc.make_links_absolute(base_url=get_base_url(url))
        for a in doc('h3 a').items():
            if a.text() == 'Join Now to Follow':
                continue
            urls.append(a.attr('href'))
        max_ = 10
        random.shuffle(urls)
        for url in urls[:max_]:
            try:
                _scrape_feed(
                    url,
                    verbose=verbose,
                )
            except NotFound:
                print("WARNING Can't find {}".format(url))
        # Now find the next pages
        if depth < 5:
            next_urls = []
            for a in doc('.pagination a').items():
                if '?page=' in a.attr('href'):
                    next_urls.append(a.attr('href'))
            random.shuffle(urls)
            for next_url in next_urls[:max_]:
                for podcast in find_podcasts(
                    next_url,
                    verbose=verbose,
                    depth=depth + 1
                ):
                    yield podcast
    else:
        try:
            html = download(url)
        except ConnectionError:
            return
        doc = pyquery.PyQuery(html)
        doc.make_links_absolute(base_url=get_base_url(url))
        for a in doc('ul.nav ul.dropdown-menu li a'):
            href = a.attrib['href']
            if '/browse/' in href:
                urls.append(url)

        max_ = 10
        random.shuffle(urls)
        for url in urls[:max_]:
            yield _scrape_index(
                url,
                verbose=verbose,
                max_=max_,
            )


def _scrape_feed(url, verbose=False):
    html = download(url, gently=True)
    doc = pyquery.PyQuery(html)
    doc.make_links_absolute(get_base_url(url))
    print("URL:", url)
    for a in doc('.span3 li a').items():
        if a.text() == 'RSS':
            feed_url = a.attr('href')
            response = requests.head(feed_url)
            if response.status_code in (301, 302):
                feed_url = response.headers['Location']
            if '://' not in feed_url:
                feed_url = 'http://' + feed_url
            if Podcast.objects.filter(url=feed_url).exists():
                # print "ALREADY HAD", feed_url
                continue
            try:
                image_url = get_image_url(feed_url)
            except ConnectionError:
                print('Unable to download image for {}'.format(feed_url))
                continue
            except ExpatError:
                print('ExpatError when getting image on {}'.format(feed_url))
                continue
            except NotXMLResponse:
                print(
                    'NotXMLResponse when getting image on {}'.format(feed_url)
                )
                continue
            if not image_url:
                print("Skipping (no image)", feed_url)
                continue
            if image_url.startswith('//'):
                if urlparse(feed_url).scheme == 'https':
                    image_url = 'https:' + image_url
                else:
                    image_url = 'http:' + image_url
            assert '://' in image_url, image_url
            podcast = Podcast.objects.create(
                url=feed_url,
                image_url=image_url,
            )
            return podcast


def _scrape_index(url, verbose=False, max_=1000):
    html = download(url, gently=True)
    doc = pyquery.PyQuery(html)
    links = doc('.thumbnails a')
    shows = []
    for link in links:
        show_url = link.attrib['href']
        show_url = urljoin(url, show_url)
        link = pyquery.PyQuery(link)
        for h4 in link.find('h4'):
            name = h4.text_content()
        shows.append((name, show_url))

    existing_names = Podcast.objects.all().values_list('name', flat=True)

    # XXX might not keep this
    shows = [
        (n, u) for (n, u) in shows
        if n not in existing_names
    ]
    random.shuffle(shows)
    for name, show_url in shows[:max_]:
        rss_url = _scrape_show(show_url)
        if not rss_url:
            print("Skipping", name, show_url)
            continue

        image_url = get_image_url(rss_url)
        if not image_url:
            print("Skipping (no image)", name, rss_url)
            continue
        assert '://' in image_url, image_url

        try:
            podcast = Podcast.objects.get(name=name)
            podcast.url = rss_url
            podcast.image_url = image_url
            podcast.save()
            created = False
        except Podcast.DoesNotExist:
            assert name, rss_url
            podcast = Podcast.objects.create(
                name=name,
                url=rss_url,
                image_url=image_url,
            )
            created = True
        try:
            podcast.download_image()
        except (AssertionError, NotAnImageError):
            if verbose:
                print("Got an error trying to download the image :(")
                print("IGNORING AND MOVING ON")
            PodcastError.create(podcast)

        if verbose:
            if created:
                print("CREATED")
            else:
                print("NOT NEW")
            print(repr(name))


def _scrape_show(url):
    try:
        html = download(url)
    except (ConnectionError, ReadTimeout):
        return
    doc = pyquery.PyQuery(html)
    for a in doc('.sidebar-nav a'):
        for h4 in pyquery.PyQuery(a).find('h4'):
            if h4.text_content() == 'Open RSS feed':
                rss_url = urljoin(url, a.attrib['href'])
                return rss_url


def fix_podcast_images(max_, verbose=False):
    podcasts = Podcast.objects.filter(
        image__isnull=True,
        image_url__isnull=False,
        itunes_lookup__isnull=False,
    )

    for podcast in podcasts.order_by('?')[:max_]:
        print(repr(podcast.name))
        print(podcast.image)
        print(podcast.image_url)
        print(podcast.itunes_lookup['artworkUrl600'])
        print()
        raise NotImplementedError
