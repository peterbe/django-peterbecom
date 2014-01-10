from django.db import models
from peterbecom.apps.plog import utils


class Result(models.Model):
    url = models.URLField(max_length=400)
    count = models.IntegerField()
    add_date = models.DateTimeField(default=utils.utc_now)


class ResultDomain(models.Model):
    result = models.ForeignKey(Result)
    domain = models.CharField(max_length=100)
