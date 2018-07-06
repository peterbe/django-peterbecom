# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="BootMeasurement",
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
                ("time_to_boot1", models.FloatField()),
                ("time_to_boot2", models.FloatField()),
                ("plain_localstorage", models.BooleanField(default=False)),
                ("driver", models.CharField(max_length=250, null=True, blank=True)),
                ("user_agent", models.CharField(max_length=250, null=True, blank=True)),
                ("add_date", models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={},
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name="Measurement",
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
                ("url", models.URLField()),
                ("user_agent", models.CharField(max_length=250)),
                ("driver", models.CharField(max_length=250, null=True, blank=True)),
                ("xhr_median", models.FloatField()),
                ("local_median", models.FloatField()),
                ("plain_localstorage", models.BooleanField(default=False)),
                ("iterations", models.PositiveIntegerField()),
                ("add_date", models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={},
            bases=(models.Model,),
        ),
    ]
