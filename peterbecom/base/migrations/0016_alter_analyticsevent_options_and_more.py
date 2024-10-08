# Generated by Django 4.2.15 on 2024-10-07 11:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0015_analyticsreferrerevent'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='analyticsevent',
            options={'verbose_name': 'Analytics event'},
        ),
        migrations.AddIndex(
            model_name='analyticsevent',
            index=models.Index(condition=models.Q(('type', 'pageview')), fields=['created'], name='base_analyticsevent_created'),
        ),
    ]
