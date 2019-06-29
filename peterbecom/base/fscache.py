import os
import random
import re
import time
from urllib.parse import urljoin, urlparse

import backoff
import requests
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.cache import cache
from huey.contrib.djhuey import task

from peterbecom.base.models import CDNPurgeURL


class EmptyFSCacheFile(Exception):
    """No fscache written file should ever be 0 bytes."""


def path_to_fs_path(path):
    fs_path = settings.FSCACHE_ROOT
    for directory in path.split("/"):
        if directory:
            fs_path = os.path.join(fs_path, directory)
    return fs_path + "/index.html"


def create_parents(fs_path):
    directory = os.path.dirname(fs_path)
    here = settings.FSCACHE_ROOT
    for part in directory.replace(settings.FSCACHE_ROOT, "").split("/"):
        here = os.path.join(here, part)
        if not os.path.isdir(here):
            try:
                os.mkdir(here)
                os.chmod(here, 0o755)
            except FileExistsError:
                # Race conditions
                pass


def too_old(fs_path, seconds):
    age = time.time() - os.stat(fs_path).st_mtime
    return age > seconds


def _invalidate(fs_path):
    assert "//" not in fs_path, fs_path
    deleted = []
    if os.path.isfile(fs_path):
        attempts = 0
        while attempts < 3:
            try:
                os.remove(fs_path)
                deleted.append(fs_path)
                break
            except FileNotFoundError:
                # race condition probably.
                pass

    endings = (".metadata", ".cache_control", ".gz", ".br", ".original")
    for ending in endings:
        fs_path_w = fs_path + ending
        if os.path.isfile(fs_path_w):
            attempts = 0
            while attempts < 3:
                try:
                    os.remove(fs_path_w)
                    deleted.append(fs_path_w)
                    break
                except FileNotFoundError:
                    # race condition probably.
                    pass

    return deleted


def invalidate_by_url(url, revisit=False):
    if not url.startswith("/"):
        url = urlparse(url).path
    if not url.endswith("/"):
        url += "/"
    fs_path = settings.FSCACHE_ROOT + url + "index.html"
    deleted = _invalidate(fs_path)
    if revisit:
        revisit_url(fs_path)
    return deleted


def invalidate_by_url_soon(urls):
    if not urls:
        return
    if isinstance(urls, str):
        urls = [urls]
    slated = cache.get("invalidate_by_url", [])
    for url in urls:
        if url not in slated:
            slated.append(url)

    cache.set("invalidate_by_url", slated, 60)
    # The added jitter to the delay is there to avoid race conditions.
    # If this task is sent twice (which can happen) and two Huey workers
    # (two completely separate workers/threads) both start at the same time
    # they might both do...
    #   Timestamp 1 Thread 1. Get URLs from cache, got 5
    #   Timestamp 2 Thread 2. Get URLs from cache, got 5
    #   Timestamp 3 Thread 1. Got it, now delete from the cache
    #   ...
    # That means that second thread that is a millisecond behind, gets the same
    # result as the first thread one when it asks the cache because thread one
    # hasn't yet had a chance to tell it to delete.
    invalidate_by_url_later.schedule((), delay=3 + 2 * random.random())


@task()
def invalidate_by_url_later():
    # Order preserving uniqify list
    _seen = set()
    slated = [
        x
        for x in cache.get("invalidate_by_url", [])
        if x not in _seen and not _seen.add(x)
    ]
    if slated:
        cache.delete("invalidate_by_url")
        for url in slated:
            invalidate_by_url(url, revisit=True)
        CDNPurgeURL.add(slated)


def delete_empty_directory(filepath):
    dirpath = os.path.dirname(filepath)
    if not os.listdir(dirpath):
        os.rmdir(dirpath)


def revisit_url(path, verbose=False):
    path = path.replace("/index.html", "")
    path = path.replace(settings.FSCACHE_ROOT, "")
    site = Site.objects.get_current()
    secure = getattr(settings, "FSCACHE_SECURE_SITE", True)
    base_url = secure and "https://" or "http://"
    base_url += site.domain
    url = urljoin(base_url, path)
    response = requests.get(url)
    if verbose:
        print("REVISITED", url, response.status_code)


def invalidate_too_old(verbose=False, dry_run=False, revisit=False):
    found = []
    deleted = []
    for root, dirs, files in os.walk(settings.FSCACHE_ROOT):
        for file_ in files:
            if file_.endswith(".metadata"):
                continue
            path = os.path.join(root, file_)
            if (
                "index.html" in file_
                and os.path.isfile(path)
                and not os.stat(path).st_size
            ):
                raise EmptyFSCacheFile(path)
            if os.path.isfile(path + ".metadata"):
                found.append(os.stat(path).st_size)
                seconds = None
                if os.path.isfile(path + ".cache_control"):
                    with open(path + ".cache_control") as seconds_f:
                        seconds = int(seconds_f.read())
                if too_old(path, seconds):
                    if verbose:
                        print("INVALIDATE", path)
                    if not dry_run:
                        found.append(os.stat(path).st_size)
                        these_deleted = _invalidate(path)
                        deleted.extend(these_deleted)
                        if verbose:
                            print("\tDELETED", these_deleted)
                        delete_empty_directory(path)
                        if revisit:
                            revisit_url(path, verbose=verbose)
                # elif verbose:
                #     print('NOT TOO OLD', path)
        if not files and not os.listdir(root):
            if verbose:
                print("NO FILES IN", root)
            if not dry_run:
                os.rmdir(root)

    if verbose:
        print("Found {:,} possible files".format(len(found)))
        mb = sum(found) / 1024.0 / 1024.0
        print("Totalling", "%.1f MB" % mb)
        print("Deleted {:,} files".format(len(deleted)))


def cache_request(request, response):
    if not settings.FSCACHE_ROOT:
        # bail if it hasn't been set up
        return False
    if (
        request.method == "GET"
        and
        # request.path != '/' and
        response.status_code == 200
        and not request.META.get("QUERY_STRING")
        and
        # XXX TODO: Support JSON and xml
        "text/html" in response["Content-Type"]
    ):
        # When you have url patterns like `/foo/(?P<oid>.*)` you can get requests
        # that match but if the URL is something like
        # "/foo/myslug%0Anextline" which translates to `/foo/myslug\nnextline`.
        # The Django view will match just fine but the request.path will have a
        # `\s` character in it.
        # If that's the case we don't want to cache this request.
        if "\n" in request.path or "\t" in request.path:
            return False

        # let's iterate through some exceptions
        not_starts = (
            "/plog/edit/",
            "/stats/",
            "/search",
            "/ajaxornot",
            "/localvsxhr",
            "/auth",
            "/podcasttime",
            "/nodomain",
        )
        for s in not_starts:
            if request.path.startswith(s):
                return False

        not_ends = ("/ping",)
        for s in not_ends:
            if request.path.endswith(s):
                return False

        if getattr(request, "_fscache_disable", None):
            # For some reason, the request decided this page should not
            # be FS cached.
            return False

        return True

    return False


@backoff.on_exception(
    backoff.constant, requests.exceptions.RequestException, max_tries=3
)
def _download_cdn_url(url):
    return requests.get(url)


def purge_outdated_cdn_urls(verbose=False, dry_run=False, revisit=False, max_files=100):
    """Periodically, go through fs cache files, by date, and compare each one
    with their CDN equivalent to see if the CDN version is too different.
    """
    paths = []
    for root, dirs, files in os.walk(settings.FSCACHE_ROOT):
        for file_ in files:
            if file_.endswith(".metadata"):
                continue
            path = os.path.join(root, file_)
            for attempt in range(3):
                if (
                    "index.html" in file_
                    and os.path.isfile(path)
                    and not os.stat(path).st_size
                ):
                    # If this happens, give it "one more chance" by sleeping
                    # a little and only raise the error if it file still isn't
                    # there after some sleeping.
                    time.sleep(1)
                    continue
                break
            else:
                raise EmptyFSCacheFile(path)
            if os.path.isfile(path + ".metadata") and "/awspa" not in path:
                paths.append((os.stat(path).st_mtime, path))

    # Oldest first
    paths.sort()

    for mtime, path in paths[:max_files]:
        uri = path.replace(settings.FSCACHE_ROOT, "")
        uri = re.sub(r"/index\.html$", "", uri)

        if verbose:
            age_seconds = time.time() - mtime
            if age_seconds > 10000:
                human_age = "{} hours".format(int(age_seconds / 60 / 60))
            elif age_seconds > 60:
                human_age = "{} minutes".format(int(age_seconds / 60))
            else:
                human_age = "{:.1f} seconds".format(age_seconds)
            print("{} last touched {} ago".format(uri, human_age))

        # Update the files modification time so it gets last in the sort order
        # next time.
        os.utime(path, (os.stat(path).st_atime, time.time()))

        cdn_url = "https://{}{}".format(settings.KEYCDN_HOST, uri)
        response = _download_cdn_url(cdn_url)
        if response.status_code != 200:
            if verbose:
                print("{} on {} :(".format(response.status_code, cdn_url))
            continue

        if response.headers.get("x-cache") != "HIT":
            if verbose:
                print(
                    "Wasn't x-cache HIT anyway ({!r}) {}".format(
                        response.headers.get("x-cache"), cdn_url
                    )
                )
            continue

        with open(path) as f:
            local_html = f.read()
        remote_html = response.text

        if local_html != remote_html and not dry_run:
            CDNPurgeURL.add(cdn_url)


def find_missing_compressions(verbose=False, revisit=False, max_files=500):
    deleted = revisits = 0
    for root, dirs, files in os.walk(settings.FSCACHE_ROOT):
        for file_ in files:
            if file_.endswith(".metadata"):
                continue
            path = os.path.join(root, file_)
            if (
                "index.html" in file_
                and os.path.isfile(path)
                and not os.stat(path).st_size
            ):
                print("HAD TO DELETE {}".format(path))
                os.remove(path)
                deleted += 1
                continue
            if os.path.isfile(path + ".metadata"):
                # If it ends with .metadata it has to be the index.html
                assert os.path.basename(path) == "index.html", os.path.basename(path)

                if not os.path.isfile(path + ".br") and "awspa/" not in path:
                    if verbose:
                        print("{} didn't exist!".format(path + ".br"))
                    os.remove(path)
                    deleted += 1
                    print("HAD TO DELETE {} BECAUSE .br FILE DOESNT EXIST".format(path))
                elif not os.path.isfile(path + ".gz"):
                    if verbose:
                        print("{} didn't exist!".format(path + ".gz"))
                    os.remove(path)
                    deleted += 1
                    print("HAD TO DELETE {} BECAUSE .gz FILE DOESNT EXIST".format(path))
                else:
                    continue

                if revisit:
                    revisit_url(path, verbose=verbose)
                    revisits += 1

    if verbose:
        print("Deleted {:,} files and revisited {:,} paths".format(deleted, revisit))
