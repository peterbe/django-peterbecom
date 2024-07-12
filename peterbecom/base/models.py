import datetime
import json
import sys
import traceback
from io import StringIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import ArrayField
from django.db import models, transaction
from django.db.models import F
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from peterbecom.base.utils import send_pulse_message


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


@receiver(post_save, sender=PostProcessing)
def send_post_processing_pulse(sender, instance, **kwargs):
    # The duration gets set when the post processing is done.
    if not kwargs.get("created") and instance.duration:
        send_pulse_message(
            {
                "post_processed": {
                    "filepath": instance.filepath,
                    "url": instance.url,
                    "original_url": instance.original_url,
                    "duration": instance.duration.total_seconds(),
                    "notes": instance.notes,
                    "exception": instance.exception,
                }
            }
        )


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
        return f"{self.q!r} found {self.documents_found:,} in {self.search_time.total_seconds()*1000:.1f}ms"


@receiver(post_save, sender=SearchResult)
def send_search_result_pulse_message(sender, instance, **kwargs):
    if kwargs.get("created"):
        send_pulse_message(
            {"searched": {"q": instance.q, "documents_found": instance.documents_found}}
        )


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
        cls.pulse_about_queue_count()

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
        cls.pulse_about_queue_count()

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
                raise ValueError(
                    "Only add pathnames, not absolute URLs ({!r})".format(url)
                )
            if not url.startswith("/"):
                raise ValueError("{} doesn't start with /".format(url))

    @classmethod
    def pulse_about_queue_count(cls):
        count = cls.objects.filter(
            cancelled__isnull=True, processed__isnull=True
        ).count()
        send_pulse_message({"cdn_purge_urls": count})

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
    uuid = models.CharField(max_length=400)
    url = models.CharField(max_length=400)
    created = models.DateTimeField(auto_now_add=True)
    meta = models.JSONField(default=dict)
    data = models.JSONField(default=dict)
