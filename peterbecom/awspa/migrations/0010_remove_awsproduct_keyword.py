# Generated by Django 3.1.3 on 2020-11-05 16:57

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('awspa', '0009_remove_awsproduct_paapiv5'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='awsproduct',
            name='keyword',
        ),
    ]
