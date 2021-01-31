from django.db import models
from django.utils import timezone
from django.db.models import F


class CatchallURL(models.Model):
    path = models.CharField(max_length=400, unique=True)
    count = models.PositiveIntegerField(default=1)
    created = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    @classmethod
    def upsert(cls, path):
        if not cls.objects.filter(path=path).update(
            count=F("count") + 1, last_seen=timezone.now()
        ):
            cls.objects.create(path=path)
