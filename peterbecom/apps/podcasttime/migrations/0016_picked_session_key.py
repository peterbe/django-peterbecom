# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('podcasttime', '0015_auto_20160307_1522'),
    ]

    operations = [
        migrations.AddField(
            model_name='picked',
            name='session_key',
            field=models.CharField(default=b'legacy', max_length=32),
            preserve_default=True,
        ),
    ]
