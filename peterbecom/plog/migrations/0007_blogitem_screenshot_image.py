# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import sorl.thumbnail.fields
import peterbecom.plog.models


class Migration(migrations.Migration):

    dependencies = [("plog", "0006_auto_20160818_1556")]

    operations = [
        migrations.AddField(
            model_name="blogitem",
            name="screenshot_image",
            field=sorl.thumbnail.fields.ImageField(
                null=True, upload_to=peterbecom.plog.models._upload_to_blogitem
            ),
        )
    ]
