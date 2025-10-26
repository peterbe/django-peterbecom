import datetime
import json
import sys
import traceback
from io import StringIO
from typing import TypedDict

import backoff
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import ArrayField
from django.db import models, transaction
from django.db.models import Count, F
from django.db.models.signals import pre_save
from django.db.utils import InterfaceError
from django.dispatch import receiver
from django.utils import timezone


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
    VALID_TYPES = {
        "lyrics-featureflag",
        "publicapi-pageview",
        "songsearch-autocomplete",
        "search",
        "search-error",
        "pageview",
        "logo",
    }

    type = models.CharField(max_length=100)
    uuid = models.UUIDField()
    url = models.URLField(max_length=500)
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    meta = models.JSONField(default=dict)
    data = models.JSONField(default=dict)

    class Meta:
        verbose_name = "Analytics event"


class AnalyticsRollupsDaily(models.Model):
    day = models.DateTimeField(db_index=True)
    count = models.IntegerField()
    type = models.CharField(max_length=100)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Analytics Rollups daily"

    @classmethod
    def rollup(cls, day=None):
        if not day:
            # Use yesterday
            day = timezone.now() - datetime.timedelta(days=1)

        start_of_day = day.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + datetime.timedelta(days=1)

        day = start_of_day
        print(f" ROLLUP DAY: {day.isoformat()} ".center(80, "-"))
        with transaction.atomic():
            cls.objects.filter(day=day).delete()

            agg_query = (
                AnalyticsEvent.objects.filter(
                    created__gte=start_of_day, created__lt=end_of_day
                )
                .values("type")
                .annotate(count=Count("id"))
            )
            agg_query = agg_query.order_by("type", "-count")
            bulk = []
            for agg in agg_query:
                print(f"{agg['count']:>5} {agg['type']:<20}")
                bulk.append(cls(day=day, count=agg["count"], type=agg["type"]))
                if len(bulk) > 100:
                    cls.objects.bulk_create(bulk)
                    bulk = []
            cls.objects.bulk_create(bulk)


class AnalyticsRollupsPathnameDaily(models.Model):
    day = models.DateTimeField(db_index=True)
    count = models.IntegerField()
    pathname = models.CharField(max_length=300)
    type = models.CharField(max_length=100)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Analytics Rollups by Pathname daily"

    @classmethod
    def rollup(cls, day=None):
        if not day:
            # Use yesterday
            day = timezone.now() - datetime.timedelta(days=1)

        start_of_day = day.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + datetime.timedelta(days=1)

        day = start_of_day
        print(f" ROLLUP BY PATHNAME DAY: {day.isoformat()} ".center(80, "-"))
        with transaction.atomic():
            cls.objects.filter(day=day).delete()

            agg_query = (
                AnalyticsEvent.objects.filter(
                    created__gte=start_of_day,
                    created__lt=end_of_day,
                    data__pathname__isnull=False,
                )
                .values("type", "data__pathname")
                .annotate(count=Count("id"))
            )
            agg_query = agg_query.order_by("-count")
            bulk = []
            for agg in agg_query:
                print(f"{agg['count']:>5} {agg['type']:<12} {agg['data__pathname']}")
                bulk.append(
                    cls(
                        day=day,
                        count=agg["count"],
                        type=agg["type"],
                        pathname=agg["data__pathname"],
                    )
                )
                if len(bulk) > 100:
                    cls.objects.bulk_create(bulk)
                    bulk = []
            cls.objects.bulk_create(bulk)


class AnalyticsRollupCommentsReferrerDaily(models.Model):
    day = models.DateTimeField(db_index=True)
    count = models.IntegerField()
    referrer = models.URLField()
    pathname = models.CharField(max_length=300)
    is_bot = models.BooleanField()
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Analytics Rollup Comments by Referrer and Pathname daily"

    @classmethod
    def rollup(cls, day=None):
        if not day:
            # Use yesterday
            day = timezone.now() - datetime.timedelta(days=1)

        start_of_day = day.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + datetime.timedelta(days=1)

        day = start_of_day
        print(f" ROLLUP BY PATHNAME DAY: {day.isoformat()} ".center(80, "-"))
        with transaction.atomic():
            cls.objects.filter(day=day).delete()

            agg_query = (
                AnalyticsEvent.objects.filter(
                    created__gte=start_of_day,
                    created__lt=end_of_day,
                    type="pageview",
                    data__is_comment=True,
                    # data__referrer__isnull=False,
                    data__pathname__isnull=False,
                    data__is_bot__isnull=False,
                )
                .values("data__referrer", "data__pathname", "data__is_bot")
                .annotate(count=Count("id"))
                .order_by("-count")
            )
            bulk = []
            for agg in agg_query:
                print(
                    f"{agg['count']:>5} {agg['data__referrer'] or '':<12} {agg['data__pathname']:<12} is_bot={agg['data__is_bot']}"
                )
                bulk.append(
                    cls(
                        day=day,
                        count=agg["count"],
                        referrer=agg["data__referrer"] or "",
                        is_bot=agg["data__is_bot"],
                        pathname=agg["data__pathname"],
                    )
                )
                if len(bulk) > 100:
                    cls.objects.bulk_create(bulk)
                    bulk = []
            cls.objects.bulk_create(bulk)


class AnalyticsGeoEvent(models.Model):
    event = models.OneToOneField(AnalyticsEvent, on_delete=models.CASCADE)
    ip_address = models.GenericIPAddressField()
    country_code = models.CharField(max_length=2, null=True)
    region = models.CharField(max_length=10, null=True)
    city = models.CharField(max_length=100, null=True)
    country = models.CharField(max_length=100, null=True)
    latitude = models.FloatField(null=True)
    longitude = models.FloatField(null=True)
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    lookup = models.JSONField(default=dict)


class AnalyticsReferrerEvent(models.Model):
    event = models.OneToOneField(AnalyticsEvent, on_delete=models.CASCADE)
    referrer = models.URLField(max_length=500)
    pathname = models.URLField(max_length=300, null=True)
    direct = models.BooleanField(default=False)
    search_engine = models.CharField(max_length=100, null=True)
    search = models.CharField(max_length=300, null=True)
    created = models.DateTimeField(auto_now_add=True, db_index=True)


@backoff.on_exception(backoff.expo, InterfaceError, max_time=10)
def create_event(type: str, uuid: str, url: str, meta: dict, data: dict):
    AnalyticsEvent.objects.create(
        type=type,
        uuid=uuid,
        url=url,
        meta=meta,
        data=data,
    )


class EventSignature(TypedDict):
    type: str
    uuid: str
    url: str
    meta: dict
    data: dict


@backoff.on_exception(backoff.expo, InterfaceError, max_time=10)
def bulk_create_events(data: list[EventSignature]):
    bulk = []
    for event in data:
        bulk.append(
            AnalyticsEvent(
                type=event["type"],
                uuid=event["uuid"],
                url=event["url"],
                meta=event["meta"],
                data=event["data"],
            )
        )
    AnalyticsEvent.objects.bulk_create(bulk)


class RequestLog(models.Model):
    url = models.URLField(max_length=500)
    status_code = models.IntegerField()
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    request = models.JSONField(default=dict)
    response = models.JSONField(default=dict)
    meta = models.JSONField(default=dict)


class RequestLogRollupsBotAgentStatusCodeDaily(models.Model):
    day = models.DateTimeField(db_index=True)
    count = models.IntegerField()
    bot_agent = models.CharField(max_length=100, null=True)
    status_code = models.IntegerField()
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = " RequestLog Rollups by Bot Agent and Status Code daily"

    @classmethod
    def rollup(cls, day=None):
        if not day:
            # Use yesterday
            day = timezone.now() - datetime.timedelta(days=1)

        start_of_day = day.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + datetime.timedelta(days=1)

        day = start_of_day
        print(
            f" ROLLUP BY BOTAGENT BY STATUS CODE DAY: {day.isoformat()} ".center(
                80, "-"
            )
        )
        with transaction.atomic():
            cls.objects.filter(day=day).delete()

            agg_query = (
                RequestLog.objects.filter(
                    created__gte=start_of_day,
                    created__lt=end_of_day,
                )
                .extra(where=["meta->>'botAgent' IS NOT NULL"])
                .values("status_code", "meta__botAgent")
                .annotate(count=Count("id"))
            )
            agg_query = agg_query.order_by("-count")
            bulk = []
            for agg in agg_query:
                print(
                    f"{agg['count']:>5} {agg['status_code']:<3} {agg['meta__botAgent']}"
                )
                bulk.append(
                    cls(
                        day=day,
                        count=agg["count"],
                        status_code=agg["status_code"],
                        bot_agent=agg["meta__botAgent"],
                    )
                )
                if len(bulk) > 100:
                    cls.objects.bulk_create(bulk)
                    bulk = []
            cls.objects.bulk_create(bulk)
