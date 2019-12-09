import datetime
import functools
import gzip
import os
import re
import shutil
import sys
import time
import traceback
from io import StringIO

from django.conf import settings
from django.utils import timezone
from huey import crontab
from huey.contrib.djhuey import periodic_task, task
from requests.exceptions import ReadTimeout

from peterbecom.base import songsearch_autocomplete
from peterbecom.base.cdn import purge_cdn_urls
from peterbecom.base.decorators import lock_decorator
from peterbecom.base.models import CDNPurgeURL, PostProcessing
from peterbecom.base.xcache_analyzer import get_x_cache
from peterbecom.brotli_file import brotli_file
from peterbecom.mincss_response import has_been_css_minified, mincss_html
from peterbecom.minify_html import minify_html
from peterbecom.zopfli_file import zopfli_file


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


@task()
@measure_post_process
def post_process_cached_html(
    filepath, url, postprocessing, _start_time=None, original_url=None
):
    if _start_time:
        task_delay = time.time() - _start_time
        # print("TASK_DELAY:post_process_cached_html:", task_delay)
        # with open("/tmp/taskdelay.log", "a") as f:
        #     f.write("post_process_cached_html:{}\n".format(task_delay))
        postprocessing.notes.append("Taskdelay {:.2f}s".format(task_delay))
    # Sepearated from true work-horse below. This is so that the task will
    # *always* fire immediately.
    return _post_process_cached_html(filepath, url, postprocessing, original_url)


@lock_decorator(key_maker=lambda *args, **kwargs: args[0])
def _post_process_cached_html(filepath, url, postprocessing, original_url):
    if "\n" in url:
        raise ValueError("URL can't have a linebreak in it ({!r})".format(url))
    if url.startswith("http://testserver"):
        # do nothing. testing.
        return
    if not os.path.exists(filepath):
        postprocessing.notes.append("{} no longer exists".format(filepath))
        return
        # raise ValueError(
        #     "{!r} does not exist and can't be post-processed".format(filepath)
        # )

    attempts = 0
    with open(filepath) as f:
        html = f.read()

    if has_been_css_minified(html):
        # This function has a lock decorator on it. That essentially makes sure,
        # if fired concurrently, at the same time'ish, by two threads, only one
        # of them will run at a time. In serial. The second thread will still
        # get to run. This check is to see if it's no point running now.
        msg = "HTML ({}) already post processed".format(filepath)
        postprocessing.notes.append(msg)
        return

    # Squeezing every little byte out of it!
    # That page doesn't need the little minimalcss stats block.
    # Otherwise, the default is to include it.
    include_minimalcss_stats = "/plog/blogitem-040601-1" not in url

    optimized_html = html
    while True and not url.endswith("/awspa"):
        t0 = time.perf_counter()
        try:
            print("CALLING mincss_html FOR", original_url or url)
            optimized_html = mincss_html(
                html,
                original_url or url,
                include_minimalcss_stats=include_minimalcss_stats,
            )
            t1 = time.perf_counter()
            if optimized_html is None:
                postprocessing.notes.append(
                    "At attempt number {} the optimized HTML "
                    "became None (Took {:.1f}s)".format(attempts + 1, t1 - t0)
                )
            else:
                postprocessing.notes.append(
                    "Took {:.1f}s mincss_html HTML from {} to {}".format(
                        t1 - t0, len(html), len(optimized_html)
                    )
                )
        except ReadTimeout as exception:
            postprocessing.notes.append(
                "Timeout on mincss_html() ({})".format(exception)
            )
            optimized_html = None
            # created = False

        attempts += 1
        if optimized_html is None:
            postprocessing.notes.append(
                "WARNING! mincss_html returned None for {} ({})".format(filepath, url)
            )
            if attempts < 3:
                print("Will try again!")
                time.sleep(1)
                continue
            postprocessing.notes.append("Gave up after {} attempts".format(attempts))
            return

        try:
            shutil.move(filepath, filepath + ".original")
        except FileNotFoundError:
            postprocessing.notes.append(
                "Can't move to .original {} no longer exists".format(filepath)
            )
            return
        with open(filepath, "w") as f:
            f.write(optimized_html)
        print("mincss optimized {}".format(filepath))
        break

    try:
        (page,) = re.findall(r"/p(\d+)$", url)
        page = int(page)
    except ValueError:
        page = 1

    if "/plog/blogitem-040601-1" in url:
        songsearch_autocomplete.insert(page=page)
    else:
        t0 = time.perf_counter()
        minified_html = _minify_html(filepath, url)
        t1 = time.perf_counter()
        if not minified_html:
            postprocessing.notes.append("Calling minify_html() failed")
        postprocessing.notes.append("Took {:.1f}s to minify HTML".format(t1 - t0))

        t0 = time.perf_counter()
        _zopfli_html(minified_html and minified_html or optimized_html, filepath, url)
        t1 = time.perf_counter()
        postprocessing.notes.append("Took {:.1f}s to Zopfli HTML".format(t1 - t0))

        t0 = time.perf_counter()
        _brotli_html(minified_html and minified_html or optimized_html, filepath, url)
        t1 = time.perf_counter()
        postprocessing.notes.append("Took {:.1f}s to Brotli HTML".format(t1 - t0))

    CDNPurgeURL.add(url)


@periodic_task(crontab(minute="*"))
def run_purge_cdn_urls():
    queue = CDNPurgeURL.get()
    # The `timezone.now()` in the printed output message is to keep an eye
    # on whether the periodic task sometimes fires repeatedly in a short
    # amount of time.
    if queue:
        print(
            "{} queued CDN URLs for purging: {} ({})".format(
                len(queue), queue, timezone.now()
            )
        )
        results = purge_cdn_urls(queue)
        for result in results["result"]:
            post_process_after_cdn_purge(result["url"])
    else:
        print("No queued CDN URLs for purgning ({})".format(timezone.now()))


@task()
def post_process_after_cdn_purge(url):
    if url.endswith("/plog/blogitem-040601-1"):  # only the first page!
        # To make it slighly more possible to test from locally
        url = url.replace("http://peterbecom.local", "https://www.peterbe.com")
        print("Going to get_x_cache({!r}) soon...".format(url))
        time.sleep(5)
        x_cache_result = get_x_cache(url)
        out = []
        out.append("X-Cache Result:")
        for location_code in sorted(x_cache_result):
            result = x_cache_result[location_code]
            out.append("\t{}\t{}".format(location_code, result))
        out.append("End")
        print("\n".join(out))


def _minify_html(filepath, url):
    for _ in range(3):
        try:
            with open(filepath) as f:
                html = f.read()
            break
        except FileNotFoundError:
            # Try again in a second
            time.sleep(1)
    minified_html = minify_html(html)
    if not minified_html:
        print("Failed to minify_html({!r}, {!r}).".format(filepath, url))
        with open("/tmp/minifying-trouble.log", "a") as f:
            f.write("{}\t{}\t{}\n".format(timezone.now(), filepath, url))
        if settings.DEBUG:
            raise Exception("Minifying HTML failed")
        return
    before = len(html)
    before_gz = len(gzip.compress(html.encode("utf-8")))
    after = len(minified_html)
    after_gz = len(gzip.compress(minified_html.encode("utf-8")))
    print(
        "Minified before: {} bytes ({} gzipped), "
        "After: {} bytes ({} gzipped), "
        "Shaving {} bytes ({} gzipped)"
        "".format(
            format(before, ","),
            format(before_gz, ","),
            format(after, ","),
            format(after_gz, ","),
            format(before - after, ","),
            format(before_gz - after_gz, ","),
        )
    )
    # shutil.move(filepath, filepath.replace(".html", ".not-minified.html"))
    with open(filepath, "w") as f:
        f.write(minified_html)
    print("HTML optimized {}".format(filepath))
    return minified_html


def _zopfli_html(html, filepath, url):
    for _ in range(5):
        try:
            original_ts = os.stat(filepath).st_mtime
            original_size = os.stat(filepath).st_size
        except FileNotFoundError:
            # Try again in a second.
            time.sleep(1)
            continue
        t0 = time.time()
        new_filepath = zopfli_file(filepath)
        t1 = time.time()
        if new_filepath:
            try:
                new_size = os.stat(new_filepath).st_size
            except FileNotFoundError:
                # Race conditions probably
                print("WARNING! {} is now gone".format(filepath))
                continue
            if not new_size:
                print("WARNING! {} became 0 bytes after zopfli".format(filepath))
                os.remove(new_filepath)
                continue

            if new_size > original_size:
                print("WARNING! {} became larger after zopfli".format(filepath))
                # XXX delete it?

            print(
                "Generated {} ({} bytes, originally {} bytes) Took {:.2f}s".format(
                    new_filepath,
                    format(new_size, ","),
                    format(original_size, ","),
                    t1 - t0,
                )
            )
            if original_ts != os.stat(filepath).st_mtime:
                print(
                    "WARNING! The file {} changed during the "
                    "zopfli process.".format(filepath)
                )
                continue
            break


def _brotli_html(html, filepath, url):
    for _ in range(5):
        try:
            original_ts = os.stat(filepath).st_mtime
            original_size = os.stat(filepath).st_size
        except FileNotFoundError:
            # Try again in a second.
            time.sleep(1)
            continue
        t0 = time.time()
        new_filepath = brotli_file(filepath)
        t1 = time.time()
        if new_filepath:
            try:
                new_size = os.stat(new_filepath).st_size
            except FileNotFoundError:
                # Race conditions probably
                print("WARNING! {} is now gone".format(filepath))
                continue
            if not new_size:
                print("WARNING! {} became 0 bytes after brotli".format(filepath))
                os.remove(new_filepath)
                continue
            if new_size > original_size:
                print("WARNING! {} became larger after brotli".format(filepath))
                # XXX delete it?

            print(
                "Generated {} ({} bytes, originally {} bytes) Took {:.2f}s".format(
                    new_filepath,
                    format(new_size, ","),
                    format(original_size, ","),
                    t1 - t0,
                )
            )
            if original_ts != os.stat(filepath).st_mtime:
                print(
                    "WARNING! The file {} changed during the "
                    "brotli process.".format(filepath)
                )
                continue
            break


@periodic_task(crontab(hour="*"))
def purge_old_cdnpurgeurls():
    old = timezone.now() - datetime.timedelta(days=90)
    ancient = CDNPurgeURL.objects.filter(created__lt=old)
    deleted = ancient.delete()
    print("{:,} ANCIENT CDNPurgeURLs".format(deleted[0]))


@periodic_task(crontab(hour="*"))
def purge_old_postprocessings():
    old = timezone.now() - datetime.timedelta(days=90)
    ancient = PostProcessing.objects.filter(created__lt=old)
    deleted = ancient.delete()
    print("{:,} ANCIENT PostProcessings".format(deleted[0]))

    old = timezone.now() - datetime.timedelta(hours=1)
    stuck = PostProcessing.objects.filter(
        duration__isnull=True, exception__isnull=True, created__lt=old
    )
    deleted = stuck.delete()
    print("{} STUCK PostProcessings".format(deleted[0]))
