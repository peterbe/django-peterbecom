# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('podcasttime', '0009_auto_20160224_1530'),
    ]

    operations = [
        migrations.AlterField(
            model_name='podcast',
            name='times_picked',
            field=models.IntegerField(default=0),
            preserve_default=True,
        ),
    ]
