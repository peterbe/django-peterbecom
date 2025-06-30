import datetime
import functools
import io
import json
import sys
import time
import traceback
from io import StringIO
from pathlib import Path

from django.utils import timezone
from huey import crontab
from huey.contrib.djhuey import periodic_task, task

from peterbecom.base.analytics_geo_events import create_analytics_geo_events
from peterbecom.base.analytics_referrer_events import create_analytics_referrer_events
from peterbecom.base.cdn import purge_cdn_urls
from peterbecom.base.models import (
    CDNPurgeURL,
    PostProcessing,
    RequestLog,
    AnalyticsEvent,
)
from peterbecom.base.utils import do_healthcheck
from peterbecom.base.xcache_analyzer import get_x_cache


def measure_post_process(func):
    @functools.wraps(func)
    def inner(filepath, url, *args, **kwargs):
        record = PostProcessing.objects.create(
            filepath=filepath, url=url, original_url=kwargs.get("original_url")
        )
        t0 = time.perf_counter()
        _exception = False
        try:
            return func(filepath, url, *args, **kwargs, postprocessing=record)
        except Exception:
            _exception = True
            raise
        finally:
            t1 = time.perf_counter()
            if _exception:
                etype, evalue, tb = sys.exc_info()
                out = StringIO()
                traceback.print_exception(etype, evalue, tb, file=out)
                record.exception = out.getvalue()
            record.duration = datetime.timedelta(seconds=t1 - t0)
            record.save()
            if _exception:
                raise

    return inner


@periodic_task(crontab(minute="*"))
def run_purge_cdn_urls():
    CDNPurgeURL.purge_old()
    for i in range(3):
        queue = CDNPurgeURL.get()
        # The `timezone.now()` in the printed output message is to keep an eye
        # on whether the periodic task sometimes fires repeatedly in a short
        # amount of time.
        if queue:
            queue_count = CDNPurgeURL.count()
            print(
                f"{len(queue)} (of {queue_count}) queued CDN URLs for purging: "
                f"{queue} ({timezone.now()})"
            )
            try:
                results = purge_cdn_urls(queue)

            except Exception as r:
                # XXX Why doesn't this bubble up to stdout?!
                print("EXCEPTION in purge_cdn_urls:", r)
                traceback.print_exc()
                raise
            if results:
                for url in results["all_urls"]:
                    post_process_after_cdn_purge(url)
        else:
            print(f"No queued CDN URLs for purgning ({timezone.now()})")

        time.sleep(10)


@task()
def post_process_after_cdn_purge(url):
    if "://" not in url:
        if url.startswith("/"):
            url = f"peterbecom.local{url}"
        url = f"https://{url}"
    if url.endswith("/plog/blogitem-040601-1"):  # only the first page!
        # To make it slighly more possible to test from locally
        url = url.replace("http://peterbecom.local", "https://www.peterbe.com")
        url = url.replace("https://peterbecom.local", "https://www.peterbe.com")
        url = url.replace("www-2916.kxcdn.com", "www.peterbe.com")
        print(f"Going to get_x_cache({url!r}) soon...")
        time.sleep(5)
        x_cache_result = get_x_cache(url)
        out = []
        out.append("X-Cache Result:")
        for location_code in sorted(x_cache_result):
            result = x_cache_result[location_code]
            out.append("\t{}\t{}".format(location_code, result))
        out.append("End")
        print("\n".join(out))


@periodic_task(crontab(hour="*", minute="3"))
def purge_old_cdnpurgeurls():
    old = timezone.now() - datetime.timedelta(days=30)
    ancient = CDNPurgeURL.objects.filter(created__lt=old)
    deleted = ancient.delete()
    print(f"{deleted[0]:,} ANCIENT CDNPurgeURLs deleted")


@periodic_task(crontab(hour="*", minute="2"))
def purge_old_postprocessings():
    old = timezone.now() - datetime.timedelta(days=30)
    ancient = PostProcessing.objects.filter(created__lt=old)
    count = ancient.count()
    if count:
        ancient.delete()
        print(f"{count:,} ANCIENT PostProcessings deleted")

    old = timezone.now() - datetime.timedelta(hours=1)
    stuck = PostProcessing.objects.filter(
        duration__isnull=True, exception__isnull=True, created__lt=old
    )
    deleted = stuck.delete()
    print(f"{deleted[0]:,} STUCK PostProcessings")


@periodic_task(crontab(minute="*"))
def health_check_to_disk():
    health_file = Path("/tmp/huey_health.json")
    try:
        do_healthcheck()
        with open(health_file, "w") as f:
            json.dump({"ok": True, "error": None}, f)
    except Exception:
        with open(health_file, "w") as f:
            etype, evalue, tb = sys.exc_info()
            file = io.StringIO()
            traceback.print_tb(tb, file=file)
            json.dump(
                {
                    "ok": False,
                    "error": {
                        "type": etype.__name__,
                        "value": str(evalue),
                        "traceback": file.getvalue(),
                    },
                },
                f,
            )
        raise


@periodic_task(crontab(minute="2"))
def create_analytics_geo_events_backfill():
    print(
        "(Debugging Cron) Executing create_analytics_geo_events_backfill",
        timezone.now(),
    )
    create_analytics_geo_events(max=1000)


@periodic_task(crontab(minute="3"))
def create_analytics_referrer_events_backfill():
    print(
        "(Debugging Cron) Executing create_analytics_referrer_events_backfill",
        timezone.now(),
    )
    create_analytics_referrer_events(max=1000)


@periodic_task(crontab(hour="1", minute="2"))
def delete_old_request_logs():
    old = timezone.now() - datetime.timedelta(days=60)
    RequestLog.objects.filter(created__lt=old).delete()


@periodic_task(crontab(hour="1", minute="3"))
def delete_old_analyticsevents():
    old = timezone.now() - datetime.timedelta(days=90)
    AnalyticsEvent.objects.filter(created__lt=old).delete()
