# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [("podcasttime", "0007_auto_20160222_0852")]

    operations = [
        migrations.AlterModelOptions(name="podcast", options={"ordering": ["-picked"]}),
        migrations.AddField(
            model_name="podcast",
            name="picked",
            field=models.PositiveIntegerField(default=0),
            preserve_default=True,
        ),
    ]
