# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('podcasttime', '0013_podcast_slug'),
    ]

    operations = [
        migrations.AlterField(
            model_name='podcast',
            name='name',
            field=models.CharField(max_length=200),
            preserve_default=True,
        ),
    ]
