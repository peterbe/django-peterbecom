# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('plog', '0005_remove_blogitem_keywords'),
    ]

    operations = [
        migrations.RunSQL("""
            CREATE INDEX plog_blogitem_keywords_idx
            ON plog_blogitem USING GIN(proper_keywords);
        """),
    ]
