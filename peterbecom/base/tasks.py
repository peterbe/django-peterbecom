import datetime
import functools
import gzip
import os
import shutil
import sys
import time
import traceback
from io import StringIO

from django.conf import settings
from django.utils import timezone
from huey.contrib.djhuey import task

from peterbecom.base.models import PostProcessing
from peterbecom.brotli_file import brotli_file
from peterbecom.mincss_response import mincss_html
from peterbecom.minify_html import minify_html
from peterbecom.zopfli_file import zopfli_file


def measure_post_process(func):
    @functools.wraps(func)
    def inner(filepath, url):
        record = PostProcessing.objects.create(filepath=filepath, url=url)
        t0 = time.perf_counter()
        _exception = False
        try:
            return func(filepath, url, postprocessing=record)
        except Exception as e:
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

    return inner


@task()
@measure_post_process
def post_process_cached_html(filepath, url, postprocessing):
    if url.startswith("http://testserver"):
        # do nothing. testing.
        return
    if not os.path.exists(filepath):
        raise ValueError(
            "{!r} does not exist and can't be post-processed".format(filepath)
        )

    attempts = 0
    while True:
        original_ts = os.stat(filepath).st_mtime
        with open(filepath) as f:
            html = f.read()

        t0 = time.perf_counter()
        optimized_html = mincss_html(html, url)
        t1 = time.perf_counter()
        postprocessing.notes.append(
            "mincss_html HTML from {} to {} took {:.1f}s".format(
                len(html), len(optimized_html), t1 - t0
            )
        )
        attempts += 1
        if optimized_html is None:
            print(
                "WARNING! mincss_html returned None for {} ({})".format(filepath, url)
            )
            if attempts < 3:
                print("Will try again!")
                continue
            postprocessing.notes.append("Gave up after {} attempts".format(attempts))
            return

        if original_ts != os.stat(filepath).st_mtime:
            print(
                "WARNING!! The original HTML file changed ({}) whilst "
                "running mincss_html".format(filepath)
            )
            postprocessing.notes.append("The original HTML file changed whilst running")
            continue

        shutil.move(filepath, filepath + ".original")
        with open(filepath, "w") as f:
            f.write(optimized_html)
        print("mincss optimized {}".format(filepath))
        break

    if not url.endswith("/plog/blogitem-040601-1"):
        t0 = time.perf_counter()
        minified_html = _minify_html(filepath, url)
        t1 = time.perf_counter()
        postprocessing.notes.append("Took {:.1f}s to minify HTML".format(t1 - t0))

        t0 = time.perf_counter()
        _zopfli_html(minified_html and minified_html or optimized_html, filepath, url)
        t1 = time.perf_counter()
        postprocessing.notes.append("Took {:.1f}s to Zopfli HTML".format(t1 - t0))

        t0 = time.perf_counter()
        _brotli_html(minified_html and minified_html or optimized_html, filepath, url)
        t1 = time.perf_counter()
        postprocessing.notes.append("Took {:.1f}s to Brotli HTML".format(t1 - t0))


def _minify_html(filepath, url):
    with open(filepath) as f:
        html = f.read()
    minified_html = minify_html(html)
    if not minified_html:
        print(
            "Something went horribly wrong! The minified HTML is empty! "
            "filepath={}\turl={}".format(filepath, url)
        )
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
    shutil.move(filepath, filepath.replace(".html", ".not-minified.html"))
    with open(filepath, "w") as f:
        f.write(minified_html)
    print("HTML optimized {}".format(filepath))
    return minified_html


def _zopfli_html(html, filepath, url):
    while True:
        original_ts = os.stat(filepath).st_mtime
        t0 = time.time()
        new_filepath = zopfli_file(filepath)
        t1 = time.time()
        if new_filepath:
            print(
                "Generated {} ({} bytes, originally {} bytes) Took {:.2f}s".format(
                    new_filepath,
                    format(os.stat(new_filepath).st_size, ","),
                    format(os.stat(filepath).st_size, ","),
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
    while True:
        original_ts = os.stat(filepath).st_mtime
        t0 = time.time()
        new_filepath = brotli_file(filepath)
        t1 = time.time()
        if new_filepath:
            print(
                "Generated {} ({} bytes, originally {} bytes) Took {:.2f}s".format(
                    new_filepath,
                    format(os.stat(new_filepath).st_size, ","),
                    format(os.stat(filepath).st_size, ","),
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
