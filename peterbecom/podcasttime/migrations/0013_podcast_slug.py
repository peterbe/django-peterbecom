# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [("podcasttime", "0012_podcast_itunes_lookup")]

    operations = [
        migrations.AddField(
            model_name="podcast",
            name="slug",
            field=models.SlugField(max_length=200, null=True),
            preserve_default=True,
        )
    ]
