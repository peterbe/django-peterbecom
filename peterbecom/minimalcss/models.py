from django.db import models
from django.contrib.postgres.fields import JSONField


class Minimization(models.Model):
    url = models.URLField()
    result = JSONField()
    time_took = models.FloatField()
    add_date = models.DateTimeField(auto_now_add=True)
