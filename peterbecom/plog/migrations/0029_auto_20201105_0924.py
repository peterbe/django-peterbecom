# Generated by Django 3.1.3 on 2020-11-05 15:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('plog', '0028_auto_20200229_0832'),
    ]

    operations = [
        migrations.AlterField(
            model_name='blogcomment',
            name='geo_lookup',
            field=models.JSONField(null=True),
        ),
    ]
