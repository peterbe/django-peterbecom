# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [("podcasttime", "0011_podcasterror")]

    operations = [
        migrations.AddField(
            model_name="podcast",
            name="itunes_lookup",
            field=models.JSONField(null=True),
            preserve_default=True,
        )
    ]
