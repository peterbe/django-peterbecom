# -*- coding: utf-8 -*-
# Generated by Django 1.11.5 on 2017-09-25 17:49
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
import functools
import peterbecom.plog.models


class Migration(migrations.Migration):

    dependencies = [
        ('plog', '0011_auto_20170809_0825'),
    ]

    operations = [
        migrations.CreateModel(
            name='OneTimeAuthKey',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(default=functools.partial(peterbecom.plog.models.random_string, *(16,), **{}), max_length=16)),
                ('used', models.DateTimeField(null=True)),
                ('add_date', models.DateTimeField(auto_now_add=True)),
                ('blogcomment', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='plog.BlogComment')),
                ('blogitem', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='plog.BlogItem')),
            ],
        ),
    ]
