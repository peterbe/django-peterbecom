# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2017-12-04 15:06
from __future__ import unicode_literals

from django.db import migrations


def forwards_func(apps, schema_editor):
    AWSProduct = apps.get_model("awspa", "AWSProduct")
    qs = AWSProduct.objects.all()
    for awsproduct in qs:
        if awsproduct.keyword != awsproduct.keyword.lower():
            awsproduct.keyword = awsproduct.keyword.lower()
            awsproduct.save()


class Migration(migrations.Migration):

    dependencies = [("awspa", "0003_awsproduct_disabled")]

    operations = [migrations.RunPython(forwards_func)]
