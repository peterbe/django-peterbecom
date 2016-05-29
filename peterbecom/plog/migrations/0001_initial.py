# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import peterbecom.plog.utils
import peterbecom.plog.models


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='BlogComment',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('oid', models.CharField(unique=True, max_length=100, db_index=True)),
                ('approved', models.BooleanField(default=False)),
                ('comment', models.TextField()),
                ('comment_rendered', models.TextField(null=True, blank=True)),
                ('add_date', models.DateTimeField(default=peterbecom.plog.utils.utc_now)),
                ('name', models.CharField(max_length=100, blank=True)),
                ('email', models.CharField(max_length=100, blank=True)),
                ('user_agent', models.CharField(max_length=300, null=True, blank=True)),
                ('ip_address', models.IPAddressField(null=True, blank=True)),
                ('akismet_pass', models.NullBooleanField()),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='BlogFile',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('file', models.FileField(upload_to=peterbecom.plog.models._uploader_dir)),
                ('title', models.CharField(max_length=300, null=True, blank=True)),
                ('add_date', models.DateTimeField(default=peterbecom.plog.utils.utc_now)),
                ('modify_date', models.DateTimeField(default=peterbecom.plog.utils.utc_now)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='BlogItem',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('oid', models.CharField(unique=True, max_length=100, db_index=True)),
                ('title', models.CharField(max_length=200)),
                ('alias', models.CharField(max_length=200, null=True)),
                ('bookmark', models.BooleanField(default=False)),
                ('text', models.TextField()),
                ('text_rendered', models.TextField(blank=True)),
                ('summary', models.TextField()),
                ('url', models.URLField(null=True)),
                ('pub_date', models.DateTimeField(db_index=True)),
                ('display_format', models.CharField(max_length=20)),
                ('keywords', peterbecom.plog.models.ArrayField(max_length=500)),
                ('plogrank', models.FloatField(null=True)),
                ('codesyntax', models.CharField(max_length=20, blank=True)),
                ('disallow_comments', models.BooleanField(default=False)),
                ('hide_comments', models.BooleanField(default=False)),
                ('modify_date', models.DateTimeField(default=peterbecom.plog.utils.utc_now)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='BlogItemHits',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('oid', models.CharField(unique=True, max_length=100, db_index=True)),
                ('hits', models.IntegerField(default=0)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=100)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='blogitem',
            name='categories',
            field=models.ManyToManyField(to='plog.Category'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='blogfile',
            name='blogitem',
            field=models.ForeignKey(to='plog.BlogItem'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='blogcomment',
            name='blogitem',
            field=models.ForeignKey(to='plog.BlogItem', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='blogcomment',
            name='parent',
            field=models.ForeignKey(to='plog.BlogComment', null=True),
            preserve_default=True,
        ),
    ]
