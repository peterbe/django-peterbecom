import os
import hashlib
import datetime
import unicodedata

import requests

from django.db import models
from django.core.files import File
from django.core.files.temp import NamedTemporaryFile

from sorl.thumbnail import ImageField


def _upload_path_tagged(tag, instance, filename):
    if isinstance(filename, unicode):
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
    hashed_filename = hashlib.md5(filename + str(now.microsecond)).hexdigest()
    __, extension = os.path.splitext(filename)
    return os.path.join(tag, path, hashed_filename + extension)


def _upload_to_podcast(instance, filename):
    return _upload_path_tagged('podcasts', instance, filename)


class Podcast(models.Model):
    name = models.CharField(max_length=200, unique=True)
    url = models.URLField(max_length=400)
    image_url = models.URLField(max_length=400, null=True, blank=True)
    image = ImageField(upload_to=_upload_to_podcast)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return self.name

    def download_image(self):
        print "Downloading", self.image_url
        img_temp = NamedTemporaryFile(delete=True)
        r = requests.get(self.image_url)
        assert r.status_code == 200, r.status_code
        img_temp.write(requests.get(self.image_url).content)
        img_temp.flush()
        self.image.save(
            os.path.basename(self.image_url.split('?')[0]),
            File(img_temp)
        )


class Episode(models.Model):
    podcast = models.ForeignKey(Podcast)
    duration = models.PositiveIntegerField()
    published = models.DateTimeField()
    guid = models.CharField(max_length=200)

    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('podcast', 'guid')
