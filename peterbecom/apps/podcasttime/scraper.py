import hashlib
import time
import datetime
import random
from urlparse import urljoin
from pprint import pprint

import pyquery
import feedparser

from django.utils import timezone
from django.db.models import Count

from peterbecom.apps.podcasttime.models import Podcast, Episode
from peterbecom.apps.podcasttime.utils import (
    download,
    parse_duration_ffmpeg,
    get_image_url,
)


def download_some_episodes(max_=5, verbose=False):
    # first attempt podcasts that have 0 episodes
    podcasts = Podcast.objects.all().annotate(
        subcount=Count('episode')
    ).filter(subcount=0)

    for podcast in podcasts.order_by('?')[:max_ * 2]:
        if verbose:
            print (podcast.name, podcast.last_fetch)
        download_episodes(podcast)

    # secondly, do those whose episodes have never been fetched
    podcasts = Podcast.objects.filter(
        last_fetch__isnull=True
    ).order_by('?')
    for podcast in podcasts[:max_]:
        if verbose:
            print (podcast.name, podcast.last_fetch)
        download_episodes(podcast)

    # then do the ones with the oldest updates
    podcasts = Podcast.objects.filter(
        last_fetch__isnull=False
    ).order_by('last_fetch')
    for podcast in podcasts[:max_]:
        if verbose:
            print (podcast.name, podcast.last_fetch)
        download_episodes(podcast)


def download_episodes(podcast, verbose=True):
    xml = download(podcast.url)
    d = feedparser.parse(xml)

    def get_duration(entry):
        if not entry.get('itunes_duration'):
            try:
                for link in entry['links']:
                    if link['type'] == 'audio/mpeg':
                        return parse_duration_ffmpeg(
                            link['href']
                        )
            except KeyError:
                try:
                    print entry.enclosure
                    raise Exception(entry.enclosure)
                except AttributeError:
                    # no 'itunes:duration' and no links
                    print "SKIPPING", entry
                    return
        elif entry['itunes_duration'].count(':') >= 1:
            try:
                itunes_duration = entry['itunes_duration']
                # a bug in bad podcasts
                itunes_duration = itunes_duration.replace('>', '')
                itunes_duration = itunes_duration.replace(';', '')

                itunes_duration = [
                    int(float(x)) for x in itunes_duration.split(':')
                ]
            except ValueError:
                print entry
                print repr(entry['itunes_duration'])
                raise
            duration = 0
            itunes_duration.reverse()
            duration += itunes_duration[0]  # seconds
            if len(itunes_duration) > 1:
                duration += 60 * itunes_duration[1]  # minutes
                if len(itunes_duration) > 2:
                    duration += 60 * 60 * itunes_duration[2]  # hours
            return duration
        else:
            if not entry['itunes_duration']:
                print "BUT!", xml.find('<itunes:duration')
                return
            try:
                return int(float(entry['itunes_duration']))
            except ValueError:
                pprint(entry)
                print repr(entry['itunes_duration'])
                raise

    for entry in d['entries']:
        if not entry.get('published_parsed'):
            print "Entry without a valid 'published_parsed'!"
            print entry
            print "SKIPPING"
            continue
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
                print "No guid or id. Going to use the summary."
                try:
                    guid = hashlib.md5(
                        entry.summary.encode('utf-8')
                    ).hexdigest()
                except AttributeError:
                    print "No guid or id or summary. ",
                    print "Going to use the title."
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
                print "DURATION CHANGED!!!"
            else:
                print "Duration unchanged"
            if ep.published != published:
                print "PUBLISHED CHANGED!!!"
            else:
                print "Published unchanged"
        except Episode.DoesNotExist:
            pass

        try:
            episode = Episode.objects.get(
                podcast=podcast,
                guid=guid
            )
            episode.duration = duration
            episode.published = published
            episode.save()
            print "SAVED",
        except Episode.DoesNotExist:
            episode = Episode.objects.create(
                podcast=podcast,
                duration=duration,
                published=published,
                guid=guid,
            )
            print "CREATED",
        print (
            episode.podcast.name,
            episode.guid,
            episode.duration,
            episode.published
        )
    podcast.last_fetch = timezone.now()
    podcast.save()


def find_podcasts(baseurl, verbose=False):
    html = download(baseurl)
    doc = pyquery.PyQuery(html)
    urls = []
    for a in doc('ul.nav ul.dropdown-menu li a'):
        href = a.attrib['href']
        if '/browse/' in href:
            url = urljoin(baseurl, href)
            urls.append(url)

    max_ = 10
    random.shuffle(urls)
    for url in urls[:max_]:
        _scrape_index(
            url,
            verbose=verbose,
            max_=max_,
        )


def _scrape_index(url, verbose=False, max_=1000):
    html = download(url)
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
            print "Skipping", name, show_url
            continue

        image_url = get_image_url(rss_url)
        if not image_url:
            print "Skipping (no image)", name, rss_url
            continue
        assert '://' in image_url, image_url
        # print "IMAGE_URL", image_url

        try:
            podcast = Podcast.objects.get(name=name)
            podcast.url = rss_url
            podcast.image_url = image_url
            podcast.save()
            created = False
        except Podcast.DoesNotExist:
            podcast = Podcast.objects.create(
                name=name,
                url=rss_url,
                image_url=image_url,
            )
            created = True
        try:
            podcast.download_image()
        except AssertionError:
            if verbose:
                print "Got an error trying to download the image :("
                import sys
                print sys.exc_info()
                print "IGNORING AND MOVING ON"

        if verbose:
            if created:
                print "CREATED",
            else:
                print "NOT NEW",
            print repr(name)


def _scrape_show(url):
    html = download(url)
    doc = pyquery.PyQuery(html)
    for a in doc('.sidebar-nav a'):
        for h4 in pyquery.PyQuery(a).find('h4'):
            if h4.text_content() == 'Open RSS feed':
                rss_url = urljoin(url, a.attrib['href'])
                return rss_url
