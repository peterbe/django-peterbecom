# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [("podcasttime", "0004_auto_20160218_1122")]

    operations = [
        migrations.AlterField(
            model_name="episode",
            name="guid",
            field=models.CharField(max_length=400),
            preserve_default=True,
        )
    ]
