# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import sorl.thumbnail.fields
import peterbecom.podcasttime.models


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Episode',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('duration', models.PositiveIntegerField()),
                ('published', models.DateTimeField()),
                ('guid', models.CharField(unique=True, max_length=200)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Podcast',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(unique=True, max_length=200)),
                ('url', models.URLField(max_length=400)),
                ('image_url', models.URLField(max_length=400, null=True, blank=True)),
                ('image', sorl.thumbnail.fields.ImageField(upload_to=peterbecom.podcasttime.models._upload_to_podcast)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='episode',
            name='podcast',
            field=models.ForeignKey(to='podcasttime.Podcast', on_delete=models.CASCADE),
            preserve_default=True,
        ),
    ]
