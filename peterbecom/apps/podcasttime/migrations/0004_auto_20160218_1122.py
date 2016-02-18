# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import sorl.thumbnail.fields
import peterbecom.apps.podcasttime.models


class Migration(migrations.Migration):

    dependencies = [
        ('podcasttime', '0003_auto_20160216_2132'),
    ]

    operations = [
        migrations.AlterField(
            model_name='podcast',
            name='image',
            field=sorl.thumbnail.fields.ImageField(null=True, upload_to=peterbecom.apps.podcasttime.models._upload_to_podcast),
            preserve_default=True,
        ),
    ]
