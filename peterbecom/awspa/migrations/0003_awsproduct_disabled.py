# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2017-12-04 14:35
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("awspa", "0002_auto_20171129_0745")]

    operations = [
        migrations.AddField(
            model_name="awsproduct",
            name="disabled",
            field=models.BooleanField(default=False),
        )
    ]
