from django.db import models
from peterbecom.apps.plog import utils


class Result(models.Model):
    url = models.URLField(max_length=400, unique=True)
    count = models.IntegerField()
    add_date = models.DateTimeField(default=utils.utc_now)

    def __repr__(self):
        return "<%s (%d) %r>" % (self.__class__.__name__, self.count, self.url)


class ResultDomain(models.Model):
    result = models.ForeignKey(Result)
    domain = models.CharField(max_length=100)


class Queued(models.Model):
    url = models.URLField(max_length=400)
    add_date = models.DateTimeField(default=utils.utc_now)
