from django.db import models

from django.contrib.postgres.fields import JSONField


class Card(models.Model):
    url = models.URLField(max_length=400, db_index=True)
    data = JSONField(default=dict)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
