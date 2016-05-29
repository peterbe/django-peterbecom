# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('podcasttime', '0008_auto_20160224_1515'),
    ]

    operations = [
        migrations.CreateModel(
            name='Picked',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('podcasts', models.ManyToManyField(to='podcasttime.Podcast')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterModelOptions(
            name='podcast',
            options={'ordering': ['-times_picked']},
        ),
        migrations.RenameField(
            model_name='podcast',
            old_name='picked',
            new_name='times_picked',
        ),
    ]
