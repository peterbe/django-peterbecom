# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [("podcasttime", "0002_auto_20160216_2132")]

    operations = [
        migrations.AlterUniqueTogether(
            name="episode", unique_together=set([("podcast", "guid")])
        )
    ]
