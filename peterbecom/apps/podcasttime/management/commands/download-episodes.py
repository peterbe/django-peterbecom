import datetime
import time
import os
import hashlib
import subprocess
import re
import json
from pprint import pprint

import feedparser

from django.db.models import Count
from django.core.management.base import BaseCommand
from django.utils import timezone

from peterbecom.apps.podcasttime.models import Podcast, Episode
from peterbecom.apps.podcasttime.utils import download


_MEDIA_FILE = os.path.join(
    os.path.dirname(__file__), '.mediacache.json'
)


def wrap_subprocess(command):
    print command
    return subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    ).communicate()


def parse_duration_ffmpeg(media_url):
    try:
        with open(_MEDIA_FILE) as f:
            _cache = json.load(f)
    except IOError:
        _cache = {}
    if media_url not in _cache:
        command = ['ffmpeg', '-i', media_url]
        out, err = wrap_subprocess(command)
        REGEX = re.compile('Duration: (\d+):(\d+):(\d+).(\d+)')
        matches = REGEX.findall(err)
        # if matches:
        try:
            found, = matches
        except ValueError:
            print err
            return
        hours = int(found[0])
        minutes = int(found[1])
        minutes += hours * 60
        seconds = int(found[2])
        seconds += minutes * 60
        duration = seconds + minutes * 60 + hours * 60 * 60
        _cache[media_url] = duration
        with open(_MEDIA_FILE, 'w') as f:
            json.dump(_cache, f)
    return _cache[media_url]


class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        max_ = 5

        # first attempt podcasts that have 0 episodes
        podcasts = Podcast.objects.all().annotate(
            subcount=Count('episode')
        ).filter(subcount=0)

        for podcast in podcasts.order_by('?')[:max_]:
            print repr(podcast)
            self.download_episodes(podcast)

        # then do the ones with the oldest updates
        podcasts = Podcast.objects.exclude(id__in=podcasts).order_by('?')
        for podcast in podcasts[:max_]:
            print repr(podcast)
            self.download_episodes(podcast)

    def download_episodes(self, podcast):
        xml = download(podcast.url)
        d = feedparser.parse(xml)

        def get_duration(entry):
            if 'itunes_duration' not in entry:
                # print "BUT!", xml.find('<itunes:duration')
                # if xml.find('<itunes:duration') > -1:
                #     import codecs
                #     with codecs.open('/tmp/xml.xml', 'w', 'utf-8') as f:
                #         f.write(xml)
                #         print "WROTE /tmp/xml.xml"
                #     print entry
                #     raise Exception('Should be there')
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
                # pprint(entry)
                # print entry.keys()
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
                duration += 60 * 60 * itunes_duration[0]
                duration += 60 * itunes_duration[1]
                try:
                    duration += itunes_duration[2]
                except IndexError:
                    pass
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
            if not entry['published_parsed']:
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
            try:
                guid = entry.guid
            except AttributeError:
                try:
                    guid = entry.id
                except AttributeError:
                    print "No guid or id. Going to use the summary."
                    # pprint(entry)
                    # print entry.keys()
                    guid = hashlib.md5(
                        entry.summary.encode('utf-8')
                    ).hexdigest()
                    # raise
            if duration is None:
                continue
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
            podcast.save()
            print (
                episode.podcast.name,
                episode.guid,
                episode.duration,
                episode.published
            )
