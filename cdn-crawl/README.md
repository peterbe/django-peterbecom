# cdn-crawl

Check that pages are cached in the CDN.
Depending on how you use it, it becomes a way to probe how "hot" the
CDN cache is. Also, simply running it every now and then will cause
the cache to heat up.

The test downloads the X most recent blog posts with Brotli (`Accept-Encoding`)
and after a while starts spitting out comparison stats.

## Install

Python 3 with `requests` and `pyquery` installed. Then run:

    python cdn-crawler.py

Between each `requests.get()` there's a 3 sec sleep. You can change to to,
5.5 for example like this:

    echo 5.5 > cdn-crawler-sleeptime

The stats are printed after every 10 iterations. You can change that,
for example, to 20 like this:

    echo 20 > cdn-crawler-report-every
