from django.db import models
from django.db.models import F
from django.utils import timezone


class CatchallURL(models.Model):
    path = models.CharField(max_length=400, unique=True)
    count = models.PositiveIntegerField(default=1)
    last_referer = models.URLField(max_length=400, null=True)
    created = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    @classmethod
    def upsert(cls, path, last_referer=None):
        update = {"count": F("count") + 1, "last_seen": timezone.now()}
        if last_referer:
            update["last_referer"] = last_referer[:400]
        if not cls.objects.filter(path=path).update(**update):
            cls.objects.create(path=path)
