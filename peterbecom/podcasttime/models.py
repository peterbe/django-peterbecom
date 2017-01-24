import sys
import os
import hashlib
import datetime
import traceback
import unicodedata
import time

from django.db import models
from django.db.models import Max, Sum
from django.core.files import File
from django.core.files.temp import NamedTemporaryFile
from django.dispatch import receiver
from django.core.cache import cache

from slugify import slugify
from jsonfield import JSONField
from sorl.thumbnail import ImageField
from elasticsearch.exceptions import (
    ConnectionTimeout,
    NotFoundError,
)

from peterbecom.podcasttime.utils import realistic_request
from peterbecom.base.templatetags.jinja_helpers import thumbnail
from peterbecom.podcasttime.search import PodcastDoc


class NotAnImageError(Exception):
    """when you try to download an image and it's not actually an image"""


def es_retry(callable, *args, **kwargs):
    sleep_time = kwargs.pop('_sleep_time', 1)
    attempts = kwargs.pop('_attempts', 5)
    verbose = kwargs.pop('_verbose', False)
    ignore_not_found = kwargs.pop('_ignore_not_found', False)
    try:
        return callable(*args, **kwargs)
    except (ConnectionTimeout,) as exception:
        if attempts:
            attempts -= 1
            if verbose:
                print("ES Retrying ({} {}) {}".format(
                    attempts,
                    sleep_time,
                    exception
                ))
            time.sleep(sleep_time)
        else:
            raise
    except NotFoundError:
        if not ignore_not_found:
            raise


def _upload_path_tagged(tag, instance, filename):
    if isinstance(filename, str):
        filename = (
            unicodedata
            .normalize('NFD', filename)
            .encode('ascii', 'ignore')
        )
    now = datetime.datetime.utcnow()
    path = os.path.join(
        now.strftime('%Y'),
        now.strftime('%m'),
        now.strftime('%d')
    )
    hashed_filename = hashlib.md5(
        filename + str(now.microsecond).encode('utf-8')
    ).hexdigest()
    __, extension = os.path.splitext(str(filename))
    return os.path.join(tag, path, hashed_filename + extension)


def _upload_to_podcast(instance, filename):
    return _upload_path_tagged('podcasts', instance, filename)


class Podcast(models.Model):
    name = models.CharField(max_length=200)
    url = models.URLField(max_length=400)
    image_url = models.URLField(max_length=400, null=True, blank=True)
    image = ImageField(upload_to=_upload_to_podcast, null=True)
    itunes_lookup = JSONField(null=True)
    slug = models.SlugField(max_length=200, null=True)
    times_picked = models.IntegerField(default=0)
    last_fetch = models.DateTimeField(null=True)
    error = models.TextField(null=True)
    latest_episode = models.DateTimeField(null=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-times_picked']
        unique_together = ['name', 'url']

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return '<%s: %r>' % (self.__class__.__name__, self.name)

    def to_search(self, **kwargs):
        assert self.id, self
        doc = self.to_search_doc(**kwargs)
        return PodcastDoc(meta={'id': self.id}, **doc)

    def to_search_doc(self, **kwargs):
        episodes_qs = Episode.objects.filter(podcast=self)

        if kwargs.get('duration_sums'):
            duration = kwargs['duration_sums'].get(self.id)
        else:
            duration = episodes_qs.aggregate(
                duration=Sum('duration')
            )['duration']

        if kwargs.get('episodes_count'):
            episodes_count = kwargs['episodes_count'].get(self.id)
        else:
            episodes_count = episodes_qs.count()

        doc = {
            'id': self.id,
            'slug': self.get_or_create_slug(save=False),
            'name': self.name,
            'times_picked': self.times_picked,
            'latest_episode': self.latest_episode,
            'last_fetch': self.last_fetch,
            'modified': self.modified,
            'episodes_count': episodes_count,
            'episodes_seconds': duration,
        }
        if self.image:
            try:
                doc['thumbnail_160'] = self.get_thumbnail_url(
                    '160x160',
                    quality=81,
                    upscale=False,
                    crop='center',
                )
                doc['thumbnail_348'] = self.get_thumbnail_url(
                    '348x348',
                    quality=81,
                    upscale=False,
                    crop='center',
                )
            except OSError:
                print("{!r} lacks a valid image".format(self))
        return doc

    def get_thumbnail(self, *args, **kwargs):
        assert self.image, 'podcast must have an image'
        return thumbnail(
            self.image,
            *args,
            **kwargs
        )

    def get_thumbnail_url(self, *args, **kwargs):
        return self.get_thumbnail(*args, **kwargs).url

    def download_image(self, timeout=20):
        print("Downloading", repr(self.image_url))
        img_temp = NamedTemporaryFile(delete=True)
        r = realistic_request(self.image_url, timeout=timeout)
        assert r.status_code == 200, r.status_code
        if r.headers['content-type'] == 'text/html':
            raise NotAnImageError('%s is not an image' % self.image_url)
        print('Content-Type', r.headers['content-type'])
        img_temp.write(r.content)
        img_temp.flush()
        self.image.save(
            os.path.basename(self.image_url.split('?')[0]),
            File(img_temp)
        )
        print("Saved image", self.image.size)

    @property
    def total_seconds(self):
        return Episode.objects.filter(podcast=self).aggregate(
            models.Sum('duration')
        )['duration__sum']

    def get_or_create_slug(self, save=True):
        if not self.slug:
            self.slug = slugify(self.name)
            if save:
                self.save()
        return self.slug

    def update_latest_episode(self):
        latest = Episode.objects.filter(
            podcast=self,
        ).aggregate(published=Max('published'))['published']
        if latest:
            if (
                not self.latest_episode or
                latest > self.latest_episode
            ):
                self.latest_episode = latest
                self.save()
                return True
        return False


@receiver(models.signals.post_save, sender=Podcast)
def set_slug(sender, instance, created=False, **kwargs):
    if created:
        instance.get_or_create_slug()


@receiver(models.signals.post_save, sender=Podcast)
def invalidate_episodes_meta_cache(sender, instance, **kwargs):
    cache_key = 'episodes-meta-%s' % instance.id
    cache.delete(cache_key)


@receiver(models.signals.pre_save, sender=Podcast)
def update_slug(sender, instance, **kwargs):
    if instance.slug != slugify(instance.name):
        instance.slug = slugify(instance.name)


@receiver(models.signals.post_save, sender=Podcast)
def update_es(sender, instance, **kwargs):
    doc = instance.to_search()
    if instance.error or not instance.last_fetch:
        es_retry(doc.delete, _ignore_not_found=True)
    else:
        es_retry(doc.save)


@receiver(models.signals.pre_delete, sender=Podcast)
def delete_from_es(sender, instance, **kwargs):
    doc = instance.to_search()
    es_retry(doc.delete, _ignore_not_found=True)


class PodcastError(models.Model):
    podcast = models.ForeignKey(Podcast)
    error = JSONField()
    created = models.DateTimeField(auto_now_add=True)

    @classmethod
    def create(cls, podcast, exc_info=None):
        if exc_info is None:
            exc_info = sys.exc_info()
        exc_type, exc_value, exc_tb = exc_info
        cls.objects.create(
            podcast=podcast,
            error={
                'type': repr(exc_type),
                'value': repr(exc_value),
                'traceback': ''.join(traceback.format_tb(exc_tb)),
            }
        )


class Episode(models.Model):
    podcast = models.ForeignKey(Podcast)
    duration = models.PositiveIntegerField()
    published = models.DateTimeField()
    guid = models.CharField(max_length=400)

    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('podcast', 'guid')


class Picked(models.Model):
    podcasts = models.ManyToManyField(Podcast)
    session_key = models.CharField(max_length=32, default='legacy')

    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)


@receiver(models.signals.m2m_changed, sender=Picked.podcasts.through)
def update_podcast_times_picked(sender, instance, action, **kwargs):
    if action == 'post_add':
        instance.podcasts.all().update(
            times_picked=models.F('times_picked') + 1
        )
    elif action == 'pre_clear':
        instance.podcasts.all().update(
            times_picked=models.F('times_picked') - 1
        )
