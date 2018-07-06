# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("plog", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="blogcomment",
            name="ip_address",
            field=models.GenericIPAddressField(null=True, blank=True),
        )
    ]
