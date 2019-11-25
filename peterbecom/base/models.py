import sys
import traceback
from io import StringIO
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.postgres.fields import ArrayField, JSONField
from django.db import models, transaction
from django.db.models import F
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone
from jsonfield import JSONField as LegacyJSONField


class CommandRun(models.Model):
    app = models.CharField(max_length=100)
    command = models.CharField(max_length=100)
    duration = models.DurationField()
    notes = models.TextField(null=True)
    exception = models.TextField(null=True)
    options = LegacyJSONField(default={}, null=True)
    created = models.DateTimeField(auto_now_add=True)

    def __repr__(self):
        return "<{}: {!r} {!r}{}>".format(
            self.__class__.__name__,
            self.app,
            self.command,
            self.exception and " (Errored)" or "",
        )


class PostProcessing(models.Model):
    filepath = models.CharField(max_length=400)
    url = models.URLField(max_length=400, db_index=True)
    original_url = models.URLField(max_length=400, null=True)
    duration = models.DurationField(null=True)
    notes = ArrayField(models.CharField(max_length=400), default=list)
    exception = models.TextField(null=True)
    created = models.DateTimeField(auto_now_add=True)
    previous = models.ForeignKey(
        "self",
        null=True,
        related_name="postprocessing",
        on_delete=models.CASCADE,
        db_index=False,
    )

    @classmethod
    def ongoing(cls):
        return cls.objects.filter(exception__isnull=True, duration__isnull=True)


@receiver(pre_save, sender=PostProcessing)
def set_previous(sender, instance, **kwargs):
    qs = PostProcessing.objects.filter(url=instance.url)
    if instance.id:
        qs = qs.exclude(id=instance.id)
    for previous in qs.order_by("-created")[:1]:
        instance.previous = previous


@receiver(pre_save, sender=PostProcessing)
def truncate_long_notes(sender, instance, **kwargs):
    for i, note in enumerate(instance.notes):
        if len(note) > 400:
            print(
                "WARNING! Note ({}) was too long [{}] ({!r})".format(i, len(note), note)
            )
            instance.notes[i] = note[:400]


class SearchResult(models.Model):
    q = models.CharField(max_length=400)
    original_q = models.CharField(max_length=400, null=True)
    documents_found = models.PositiveIntegerField()
    search_time = models.DurationField()
    search_times = JSONField(default=dict)
    search_terms = ArrayField(
        ArrayField(models.CharField(max_length=400), size=2, default=list), default=list
    )
    keywords = JSONField(default=dict)
    created = models.DateTimeField(auto_now_add=True)


class CDNPurgeURL(models.Model):
    # Not really a URL. Mostly a URL path (e.g. /plog/foo/bar)
    url = models.URLField(max_length=400, db_index=True)
    attempted = models.DateTimeField(null=True)
    processed = models.DateTimeField(null=True)
    cancelled = models.DateTimeField(null=True)
    attempts = models.PositiveIntegerField(default=0)
    exception = models.TextField(null=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        s = "{} id={}".format(self.url, self.id)
        facts = []
        if self.processed:
            facts.append("processed")
        if self.cancelled:
            facts.append("cancelled")
        if self.attempted:
            facts.append("attempted")
        if self.attempts:
            facts.append("{} attempts".format(self.attempts))
        if self.exception:
            facts.append("has exception!")
        if facts:
            s += " ({})".format(", ".join(facts))
        return s

    @classmethod
    def add(cls, urls):
        if isinstance(urls, str):
            urls = [urls]
        # Turn every URL into just the path
        for i, url in enumerate(urls):
            if "://" in url:
                urls[i] = urlparse(url).path
        with transaction.atomic():
            cls.objects.filter(
                url__in=urls, cancelled__isnull=True, processed__isnull=True
            ).update(cancelled=timezone.now())
            cls.objects.bulk_create([cls(url=url) for url in urls])

    @classmethod
    def get(cls, max_urls=None):
        if not max_urls:
            max_urls = settings.CDN_MAX_PURGE_URLS
        qs = cls.objects.filter(cancelled__isnull=True, processed__isnull=True)
        return list(qs.order_by("created")[:max_urls].values_list("url", flat=True))

    @classmethod
    def succeeded(cls, urls):
        if isinstance(urls, str):
            urls = [urls]
        cls.objects.filter(url__in=urls).update(processed=timezone.now())

    @classmethod
    def failed(cls, urls):
        if isinstance(urls, str):
            urls = [urls]
        etype, evalue, tb = sys.exc_info()
        out = StringIO()
        traceback.print_exception(etype, evalue, tb, file=out)
        exception = out.getvalue()
        cls.objects.filter(
            url__in=urls, processed__isnull=True, cancelled__isnull=True
        ).update(
            attempted=timezone.now(), attempts=F("attempts") + 1, exception=exception
        )
