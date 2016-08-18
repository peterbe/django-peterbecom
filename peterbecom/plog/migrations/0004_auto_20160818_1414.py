# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


def forwards_func(apps, schema_editor):
    BlogItem = apps.get_model("plog", "BlogItem")
    for blogitem in BlogItem.objects.all():
        keywords = list(set(
            x.strip() for x in blogitem.keywords if x.strip()
        ))
        blogitem.proper_keywords = keywords
        blogitem.save()


class Migration(migrations.Migration):

    dependencies = [
        ('plog', '0003_blogitem_proper_keywords'),
    ]

    operations = [
        migrations.RunPython(forwards_func),
    ]
