import gzip
import os
import shutil

from celery import shared_task

from peterbecom.mincss_response import mincss_html
from peterbecom.minify_html import minify_html


@shared_task
def post_process_cached_html(filepath, url):
    if url.startswith("http://testserver"):
        # do nothing. testing.
        return
    if not os.path.exists(filepath):
        raise ValueError(
            "{!r} does not exist and can't be post-processed".format(filepath)
        )

    with open(filepath) as f:
        html = f.read()
        optimized_html = mincss_html(html, url)
    if optimized_html is None:
        print("WARNING! mincss_html returned None for {} ({})".format(filepath, url))
        return
    # if os.path.isfile(filepath + '.original'):
    #     warnings.warn('{} was already optimized'.format(filepath))
    shutil.move(filepath, filepath + ".original")
    with open(filepath, "w") as f:
        f.write(optimized_html)
    print("mincss optimized {}".format(filepath))

    minified_html = minify_html(optimized_html)
    if not minify_html:
        print("Something went horribly wrong! The minified HTML is empty!")
        print("filepath={}\turl={}".format(filepath, url))
        return
    before = len(optimized_html)
    before_gz = len(gzip.compress(optimized_html.encode("utf-8")))
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
