# Generated by Django 2.1 on 2018-08-02 17:53

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('plog', '0015_blogitem_open_graph_image'),
    ]

    operations = [
        migrations.AlterField(
            model_name='blogitem',
            name='proper_keywords',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=100), default=list, size=None),
        ),
    ]
