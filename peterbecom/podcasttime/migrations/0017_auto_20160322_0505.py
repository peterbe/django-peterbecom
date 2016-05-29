# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


def delete_legacy_picked(apps, schema_editor):
    Picked = apps.get_model("podcasttime", "Picked")
    Picked.objects.filter(session_key='legacy').delete()
        

class Migration(migrations.Migration):

    dependencies = [
        ('podcasttime', '0016_picked_session_key'),
    ]

    operations = [
        migrations.RunPython(delete_legacy_picked),
    ]
