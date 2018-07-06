import os
import codecs
import datetime
import time
import random

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
    return better.decode("utf-8").strip()


class Command(BaseCommand):
    def _handle(self, *args, **kwargs):

        self.delete_orphan_images()
        self.reset_missing_images()
        self.fix_bmp_images()

        podcasts = Podcast.objects.filter(name="")
        self.out(podcasts.count(), "podcasts without a name")
        for podcast in podcasts:
            podcast.delete()

        podcasts = Podcast.objects.filter(latest_episode__isnull=True)
        self.out(podcasts.count(), "podcasts without latest_episode")
        for podcast in podcasts.order_by("?")[:1000]:
            if podcast.update_latest_episode():
                print("PODCAST", repr(podcast), podcast.latest_episode)

        podcasts = Podcast.objects.filter(
            latest_episode__isnull=False,
            last_fetch__isnull=False,
            last_fetch__gt=F("latest_episode"),
        )
        for podcast in podcasts.order_by("?")[:10]:
            if podcast.update_latest_episode():
                print("PODCAST", repr(podcast), podcast.latest_episode)

        yesterday = timezone.now() - datetime.timedelta(days=1)
        picks = Picked.objects.filter(created__lt=yesterday)
        deleted_picks = 0
        for pick in picks.order_by("created"):
            if pick.podcasts.all().count() <= 1:
                pick.delete()
                deleted_picks += 1
        if deleted_picks:
            self.out(deleted_picks, "deleted because they only had 1 podcast")

        for podcast in Podcast.objects.exclude(name="").order_by("?")[:100]:
            better = fix_encoding(podcast.name)
            if better != podcast.name:
                print("FROM", repr(podcast.name), "TO", repr(better))
                if Podcast.objects.filter(name=better).exists():
                    podcast.delete()
                    continue
                podcast.name = better
                podcast.save()

        podcasts = Podcast.objects.filter(
            image="", image_url__isnull=False, itunes_lookup__isnull=True
        )
        print(
            "{} podcasts without image and without itunes_lookup".format(
                podcasts.count()
            )
        )
        for podcast in podcasts.order_by("?")[:10]:
            print("Fetching itunes lookup for", repr(podcast))
            fetch_itunes_lookup.delay(podcast.id)
            time.sleep(4)

    def reset_missing_images(self):
        qs = Podcast.objects.filter(image__isnull=False).exclude(image="")
        for podcast in qs.order_by("?")[:100]:
            # print(podcast.image)
            full_path = self._make_full_path(podcast.image.path)
            # print(full_path)
            if not os.path.isfile(full_path):
                print(full_path)
                podcast.image = None
                podcast.save()
                print(repr(podcast))

    def delete_orphan_images(self):
        root = os.path.join(settings.MEDIA_ROOT or settings.BASE_DIR, "podcasts")
        images = {}
        image_extensions = (".jpg", ".jpeg", ".png", ".gif")
        image_optimizations = (
            "optimized",
            "guetzlied",
            "pillow",
            "mozjpeged",
            "pngquanted",
        )
        for root, dirs, files in os.walk(root):
            for name in files:
                f = os.path.join(root, name)
                # print("NAME", repr(name))
                if name in (".DS_Store",):
                    if os.path.isfile(name):
                        os.remove(name)
                    continue
                n = os.path.splitext(f)[1].lower()
                if n in image_extensions:
                    if f not in images:
                        images[f] = []
                elif f.split(".")[-1] in image_optimizations:
                    fn = f.rsplit(".", 1)[0]
                    if fn not in images:
                        images[fn] = []
                    images[fn].append(f)
                else:
                    print("????", f)
                    try:
                        img = Image.open(f)
                        name, _ = os.path.splitext(f)
                        new_full_path = name + ".png"
                        img.save(new_full_path)
                        old_path = self._make_relative_path(f)
                        try:
                            podcast = Podcast.objects.get(image=old_path)
                            podcast.image = self._make_relative_path(new_full_path)
                            print("NEW IMAGE PATH", podcast.image)
                            self.out("CREATED", new_full_path)
                        except Podcast.DoesNotExist:
                            pass
                    except OSError as exception:
                        self.notice("Can't convert {} ({})".format(f, exception))
                    self.out("DELETED", f)
                    os.remove(f)
                    # raise Exception
        len_images = len(images)
        self.out(len_images, "potential orphan images")
        keeps = 0
        for f in random.sample(images.keys(), min(200, len_images)):
            rel_path = self._make_relative_path(f)
            qs = Podcast.objects.filter(image__contains=rel_path)
            if not qs.exists() and os.path.isfile(f):
                print("DELETE", f)
                os.remove(f)
                for other in images[f]:
                    print("\tDELETE", other)
                    os.remove(other)
            else:
                keeps += 1
        self.out("KEEP", keeps, "images that are not orphans")

    def fix_bmp_images(self):
        # Try to convert .bmp images
        for podcast in Podcast.objects.filter(image__iendswith=".bmp"):
            print(podcast.image.path)
            if not os.path.exists(podcast.image.path):
                self.error("{} does not exist!".format(podcast.image.path))
                continue
            img = Image.open(podcast.image.path)
            w, h = img.size
            if w > 1300 or h > 1300:
                h = int(1300 * h / w)
                w = 1300
            old_path = podcast.image.path
            img.thumbnail((w, h))
            options = {"quality": 95}
            new_path = os.path.splitext(podcast.image.path)[0] + ".png"
            img.save(new_path, **options)
            new_path = self._make_relative_path(new_path)
            print("NEW_PATH", repr(new_path))
            podcast.image = new_path
            podcast.save()
            if os.path.isfile(old_path):
                self.out("DELETE", old_path)
                os.remove(old_path)

    @staticmethod
    def _make_relative_path(full_path):
        if settings.MEDIA_ROOT:
            full_path = full_path.replace(settings.MEDIA_ROOT, "")
        else:
            full_path = full_path.replace(settings.BASE_DIR, "")
        if full_path.startswith("/"):
            full_path = full_path[1:]
        return full_path

    @staticmethod
    def _make_full_path(rel_path):
        return os.path.join(settings.MEDIA_ROOT or settings.BASE_DIR, rel_path)
