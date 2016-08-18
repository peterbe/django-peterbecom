# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.contrib.postgres.fields


class Migration(migrations.Migration):

    dependencies = [
        ('plog', '0002_auto_20160530_2013'),
    ]

    operations = [
        migrations.AddField(
            model_name='blogitem',
            name='proper_keywords',
            field=django.contrib.postgres.fields.ArrayField(default=[], base_field=models.CharField(max_length=100), size=None),
        ),
    ]
