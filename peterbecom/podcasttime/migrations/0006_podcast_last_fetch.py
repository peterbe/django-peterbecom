# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('podcasttime', '0005_auto_20160218_1515'),
    ]

    operations = [
        migrations.AddField(
            model_name='podcast',
            name='last_fetch',
            field=models.DateTimeField(null=True),
            preserve_default=True,
        ),
    ]
