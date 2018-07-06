# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [("podcasttime", "0010_auto_20160225_0755")]

    operations = [
        migrations.CreateModel(
            name="PodcastError",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("error", jsonfield.fields.JSONField()),
                ("created", models.DateTimeField(auto_now_add=True)),
                (
                    "podcast",
                    models.ForeignKey(
                        to="podcasttime.Podcast", on_delete=models.CASCADE
                    ),
                ),
            ],
            options={},
            bases=(models.Model,),
        )
    ]
