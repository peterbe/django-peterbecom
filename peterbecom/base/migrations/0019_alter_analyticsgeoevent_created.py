# Generated by Django 5.2.3 on 2025-06-30 22:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0018_delete_commandrun'),
    ]

    operations = [
        migrations.AlterField(
            model_name='analyticsgeoevent',
            name='created',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
    ]
