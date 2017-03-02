# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-03-02 13:52
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('podcasttime', '0021_auto_20170301_0755'),
    ]

    operations = [
        migrations.AddField(
            model_name='podcast',
            name='link',
            field=models.URLField(max_length=400, null=True),
        ),
        migrations.AddField(
            model_name='podcast',
            name='subtitle',
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name='podcast',
            name='summary',
            field=models.TextField(null=True),
        ),
    ]
