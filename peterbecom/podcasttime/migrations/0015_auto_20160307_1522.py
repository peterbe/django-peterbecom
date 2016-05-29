# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('podcasttime', '0014_auto_20160307_1229'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='podcast',
            unique_together=set([('name', 'url')]),
        ),
    ]
