import gzip
import os
import shutil
import time

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from peterbecom.mincss_response import mincss_html
from peterbecom.minify_html import minify_html
from peterbecom.zopfli_file import zopfli_file


@shared_task
def post_process_cached_html(filepath, url):
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

        optimized_html = mincss_html(html, url)
        attempts += 1
        if optimized_html is None:
            print(
                "WARNING! mincss_html returned None for {} ({})".format(filepath, url)
            )
            if attempts < 3:
                print("Will try again!")
                continue
            return

        if original_ts != os.stat(filepath).st_mtime:
            print(
                "WARNING!! The original HTML file changed ({}) whilst "
                "running mincss_html".format(filepath)
            )
            continue

        shutil.move(filepath, filepath + ".original")
        with open(filepath, "w") as f:
            f.write(optimized_html)
        print("mincss optimized {}".format(filepath))
        break

    # Minification
    minified_html = _minify_html(filepath, url)

    # Zopfli
    _zopfli_html(minified_html and minified_html or optimized_html, filepath, url)


def _minify_html(filepath, url):
    with open(filepath) as f:
        html = f.read()
    minified_html = minify_html(html)
    if not minified_html:
        print(
            "Something went horribly wrong! The minified HTML is empty! "
            "filepath={}\turl={}".format(filepath, url)
        )
        if settings.DEBUG:
            raise Exception("Minifying HTML failed")
        with open("/tmp/minifying-trouble.log", "a") as f:
            f.write("{}\t{}\t{}\n".format(timezone.now(), filepath, url))
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
                "Generated {} ({} bytes) from {} ({} bytes) Took {:.1f}s".format(
                    new_filepath,
                    format(os.stat(new_filepath).st_size, ","),
                    filepath,
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
