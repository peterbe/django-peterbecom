import os
import codecs
import datetime
import time

import ftfy
from PIL import Image

from django.conf import settings
from django.db.models import F
from django.utils import timezone

from peterbecom.base.basecommand import BaseCommand
from peterbecom.podcasttime.models import Podcast, Picked
from peterbecom.podcasttime.tasks import fetch_itunes_lookup


def fix_encoding(s):
    s = ftfy.fix_encoding(s)
    better, _ = codecs.escape_decode(s)
    return better.decode('utf-8').strip()


class Command(BaseCommand):

    def _handle(self, *args, **kwargs):

        # Try to convert .bmp images
        for podcast in Podcast.objects.filter(image__iendswith='.bmp'):
            print(podcast.image.path)
            img = Image.open(podcast.image.path)
            w, h = img.size
            if w > 1300 or h > 1300:
                h = int(1300 * h / w)
                w = 1300
            old_path = podcast.image.path
            img.thumbnail((w, h))
            options = {
                'quality': 95,
            }
            new_path = os.path.splitext(podcast.image.path)[0] + '.png'
            img.save(new_path, **options)
            if settings.MEDIA_ROOT:
                new_path = new_path.replace(settings.MEDIA_ROOT, '')
            else:
                new_path = new_path.replace(settings.BASE_DIR, '')
            if new_path.startswith('/'):
                new_path = new_path[1:]
            print("NEW_PATH", repr(new_path))
            podcast.image = new_path
            podcast.save()
            if os.path.isfile(old_path):
                self.out("DELETE", old_path)
                os.remove(old_path)

        podcasts = Podcast.objects.filter(name='')
        self.out(podcasts.count(), 'podcasts without a name')
        for podcast in podcasts:
            podcast.delete()

        podcasts = Podcast.objects.filter(latest_episode__isnull=True)
        self.out(podcasts.count(), 'podcasts without latest_episode')
        for podcast in podcasts.order_by('?')[:1000]:
            if podcast.update_latest_episode():
                print('PODCAST', repr(podcast), podcast.latest_episode)

        podcasts = Podcast.objects.filter(
            latest_episode__isnull=False,
            last_fetch__isnull=False,
            last_fetch__gt=F('latest_episode')
        )
        for podcast in podcasts.order_by('?')[:10]:
            if podcast.update_latest_episode():
                print('PODCAST', repr(podcast), podcast.latest_episode)

        yesterday = timezone.now() - datetime.timedelta(days=1)
        picks = Picked.objects.filter(created__lt=yesterday)
        deleted_picks = 0
        for pick in picks.order_by('created'):
            if pick.podcasts.all().count() <= 1:
                pick.delete()
                deleted_picks += 1
        if deleted_picks:
            self.out(deleted_picks, 'deleted because they only had 1 podcast')

        for podcast in Podcast.objects.exclude(name='').order_by('?')[:100]:
            better = fix_encoding(podcast.name)
            if better != podcast.name:
                print("FROM", repr(podcast.name), "TO", repr(better))
                if Podcast.objects.filter(name=better).exists():
                    podcast.delete()
                    continue
                podcast.name = better
                podcast.save()

        podcasts = Podcast.objects.filter(
            image='',
            image_url__isnull=False,
            itunes_lookup__isnull=True,
        )
        print('{} podcasts without image and without itunes_lookup'.format(
            podcasts.count(),
        ))
        for podcast in podcasts.order_by('?')[:10]:
            print("Fetching itunes lookup for", repr(podcast))
            fetch_itunes_lookup.delay(podcast.id)
            time.sleep(4)
