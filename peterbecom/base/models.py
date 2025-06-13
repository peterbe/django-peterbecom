import datetime
import json
import sys
import traceback
from io import StringIO

import backoff
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import ArrayField
from django.db import models, transaction
from django.db.models import F
from django.db.models.signals import pre_save
from django.db.utils import InterfaceError
from django.dispatch import receiver
from django.utils import timezone


class CommandRun(models.Model):
    app = models.CharField(max_length=100)
    command = models.CharField(max_length=100)
    duration = models.DurationField()
    notes = models.TextField(null=True)
    exception = models.TextField(null=True)
    # options = LegacyJSONField(default={}, null=True)
    options = models.JSONField(default=dict, null=True)
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
        on_delete=models.SET_NULL,
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
    search_times = models.JSONField(default=dict)
    search_terms = ArrayField(
        ArrayField(models.CharField(max_length=400), size=2, default=list), default=list
    )
    keywords = models.JSONField(default=dict)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.q!r} found {self.documents_found:,} in {self.search_time.total_seconds() * 1000:.1f}ms"


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
        if not urls:
            return
        cls.validate_urls(urls)
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
        urls = list(qs.order_by("created")[:max_urls].values_list("url", flat=True))
        return urls

    @classmethod
    def count(cls):
        qs = cls.objects.filter(cancelled__isnull=True, processed__isnull=True)
        return qs.count()

    @classmethod
    def succeeded(cls, urls):
        if isinstance(urls, str):
            urls = [urls]
        cls.validate_urls(urls)
        cls.objects.filter(url__in=urls).update(processed=timezone.now())

    @classmethod
    def failed(cls, urls):
        if isinstance(urls, str):
            urls = [urls]
        cls.validate_urls(urls)
        etype, evalue, tb = sys.exc_info()
        out = StringIO()
        traceback.print_exception(etype, evalue, tb, file=out)
        exception = out.getvalue()
        cls.objects.filter(
            url__in=urls, processed__isnull=True, cancelled__isnull=True
        ).update(
            attempted=timezone.now(), attempts=F("attempts") + 1, exception=exception
        )

    @classmethod
    def validate_urls(cls, urls):
        for url in urls:
            if "://" in url and url.startswith("http"):
                raise ValueError(f"Only add pathnames, not absolute URLs ({url!r})")
            if not url.startswith("/"):
                raise ValueError(f"{url} doesn't start with /")

    @classmethod
    def purge_old(cls, hours=6):
        ago = timezone.now() - datetime.timedelta(hours=hours)
        count, _ = cls.objects.filter(created__lt=ago).delete()
        if count:
            print(f"Purged {count} old {cls.__name__} instances older than {ago}")


class UserProfile(models.Model):
    user = models.OneToOneField(get_user_model(), on_delete=models.CASCADE)
    claims = models.JSONField(default=dict)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User profile"

    def __str__(self):
        return json.dumps(self.claims)


class AnalyticsEvent(models.Model):
    type = models.CharField(max_length=100)
    uuid = models.UUIDField()
    url = models.URLField(max_length=500)
    created = models.DateTimeField(auto_now_add=True)
    meta = models.JSONField(default=dict)
    data = models.JSONField(default=dict)

    class Meta:
        verbose_name = "Analytics event"
        indexes = [
            models.Index(
                fields=["created"],
                name="%(app_label)s_%(class)s_created",
                condition=models.Q(type="pageview"),
            ),
        ]


class AnalyticsGeoEvent(models.Model):
    event = models.OneToOneField(AnalyticsEvent, on_delete=models.CASCADE)
    ip_address = models.GenericIPAddressField()
    country_code = models.CharField(max_length=2, null=True)
    region = models.CharField(max_length=10, null=True)
    city = models.CharField(max_length=100, null=True)
    country = models.CharField(max_length=100, null=True)
    latitude = models.FloatField(null=True)
    longitude = models.FloatField(null=True)
    created = models.DateTimeField(auto_now_add=True)
    lookup = models.JSONField(default=dict)


class AnalyticsReferrerEvent(models.Model):
    event = models.OneToOneField(AnalyticsEvent, on_delete=models.CASCADE)
    referrer = models.URLField(max_length=500)
    pathname = models.URLField(max_length=300, null=True)
    direct = models.BooleanField(default=False)
    search_engine = models.CharField(max_length=100, null=True)
    search = models.CharField(max_length=300, null=True)
    created = models.DateTimeField(auto_now_add=True)


@backoff.on_exception(backoff.expo, InterfaceError, max_time=10)
def create_event(type: str, uuid: str, url: str, meta: dict, data: dict):
    AnalyticsEvent.objects.create(
        type=type,
        uuid=uuid,
        url=url,
        meta=meta,
        data=data,
    )


class RequestLog(models.Model):
    url = models.URLField(max_length=500)
    status_code = models.IntegerField()
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    request = models.JSONField(default=dict)
    response = models.JSONField(default=dict)
    meta = models.JSONField(default=dict)
