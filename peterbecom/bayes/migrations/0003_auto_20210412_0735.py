# Generated by Django 3.2 on 2021-04-12 12:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bayes', '0002_auto_20201105_0924'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bayesdata',
            name='id',
            field=models.AutoField(primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name='blogcommenttraining',
            name='id',
            field=models.AutoField(primary_key=True, serialize=False),
        ),
    ]
