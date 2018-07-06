# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("plog", "0004_auto_20160818_1414")]

    operations = [migrations.RemoveField(model_name="blogitem", name="keywords")]
