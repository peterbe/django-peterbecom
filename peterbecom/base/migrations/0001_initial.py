# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models

# import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="CommandRun",
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
                ("command", models.CharField(max_length=100)),
                ("app", models.CharField(max_length=100)),
                ("duration", models.DurationField()),
                ("notes", models.TextField(null=True)),
                ("exception", models.TextField(null=True)),
                ("options", models.JSONField(default={}, null=True)),
                ("created", models.DateTimeField(auto_now_add=True)),
            ],
        )
    ]
