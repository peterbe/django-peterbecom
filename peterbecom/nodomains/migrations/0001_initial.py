# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import peterbecom.plog.utils


class Migration(migrations.Migration):

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Queued",
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
                ("url", models.URLField(max_length=400)),
                (
                    "add_date",
                    models.DateTimeField(default=peterbecom.plog.utils.utc_now),
                ),
            ],
            options={},
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name="Result",
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
                ("url", models.URLField(unique=True, max_length=400)),
                ("count", models.IntegerField()),
                (
                    "add_date",
                    models.DateTimeField(default=peterbecom.plog.utils.utc_now),
                ),
            ],
            options={},
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name="ResultDomain",
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
                ("domain", models.CharField(max_length=100)),
                ("count", models.PositiveIntegerField(default=1, null=True)),
                (
                    "result",
                    models.ForeignKey(to="nodomains.Result", on_delete=models.CASCADE),
                ),
            ],
            options={},
            bases=(models.Model,),
        ),
    ]
