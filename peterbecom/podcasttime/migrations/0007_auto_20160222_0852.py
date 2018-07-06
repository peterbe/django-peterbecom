# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [("podcasttime", "0006_podcast_last_fetch")]

    operations = [
        migrations.RunSQL(
            """
            CREATE INDEX podcasttime_podcast_name_fts_idx
            ON podcasttime_podcast
            USING gin(to_tsvector('english', name))
            """
        )
    ]
