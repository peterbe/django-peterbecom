# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("podcasttime", "0017_auto_20160322_0505")]

    operations = [
        migrations.AddField(
            model_name="podcast", name="error", field=models.TextField(null=True)
        )
    ]
