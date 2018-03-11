from django.db import models
from django.db.models.signals import post_save
from django.core.cache import cache
from django.dispatch import receiver

from peterbecom.plog import utils


class Result(models.Model):
    url = models.URLField(max_length=400, unique=True)
    count = models.IntegerField()
    add_date = models.DateTimeField(default=utils.utc_now)

    def __repr__(self):
        return "<%s (%d) %r>" % (self.__class__.__name__, self.count, self.url)


class ResultDomain(models.Model):
    result = models.ForeignKey(Result, on_delete=models.CASCADE)
    domain = models.CharField(max_length=100)
    count = models.PositiveIntegerField(null=True, default=1)


class Queued(models.Model):
    url = models.URLField(max_length=400)
    failed_attempts = models.PositiveIntegerField(default=0)
    add_date = models.DateTimeField(default=utils.utc_now)


@receiver(post_save, sender=Result)
def invalidate_stats_prefix(sender, instance, **kwargs):
    cache.delete('_stats_latest_add_date')
