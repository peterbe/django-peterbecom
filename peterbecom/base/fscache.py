import os
import random
import time
from urllib.parse import urljoin, urlparse

import requests
from django.core.cache import cache
from django.conf import settings
from django.contrib.sites.models import Site
from huey.contrib.djhuey import task


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
            os.mkdir(here)
            os.chmod(here, 0o755)


def too_old(fs_path, seconds=None):
    if seconds is None:
        seconds = 60 * 60 * 24  # default
        if "/plog/" in fs_path:
            seconds = 60 * 60 * 24 * 7

    age = time.time() - os.stat(fs_path).st_mtime
    return age > seconds


def invalidate(fs_path):
    assert "//" not in fs_path, fs_path
    deleted = [fs_path]
    if os.path.isfile(fs_path):
        os.remove(fs_path)
    endings = (".metadata", ".cache_control", ".gz", ".br", ".original")
    for ending in endings:
        fs_path_w = fs_path + ending
        if os.path.isfile(fs_path_w):
            os.remove(fs_path_w)
            deleted.append(fs_path_w)

    # XXX What about "index.not-minified.html"???

    return deleted


def invalidate_by_url(url, revisit=False):
    if not url.startswith("/"):
        url = urlparse(url).path
    if not url.endswith("/"):
        url += "/"
    fs_path = settings.FSCACHE_ROOT + url + "index.html"
    invalidate(fs_path)
    if revisit:
        revisit_url(fs_path)


def invalidate_by_url_soon(url):
    slated = cache.get("invalidate_by_url", [])
    slated.append(url)
    cache.set("invalidate_by_url", slated, 60)
    invalidate_by_url_later()


@task()
def invalidate_by_url_later():
    if not settings.HUEY.get("always_eager"):
        time.sleep(2 + random.random())
    slated = list(set(cache.get("invalidate_by_url", [])))
    if slated:
        cache.delete("invalidate_by_url")
    print("After sleeping, there are {} URLs to invalidate".format(len(slated)))
    for url in slated:
        invalidate_by_url(url, revisit=True)


def delete_empty_directory(filepath):
    dirpath = os.path.dirname(filepath)
    if not os.listdir(dirpath):
        os.rmdir(dirpath)


def revisit_url(path):
    path = path.replace("/index.html", "")
    path = path.replace(settings.FSCACHE_ROOT, "")
    site = Site.objects.get_current()
    secure = getattr(settings, "FSCACHE_SECURE_SITE", True)
    base_url = secure and "https://" or "http://"
    base_url += site.domain
    url = urljoin(base_url, path)
    print("REVISIT", url, requests.get(url).status_code)


def invalidate_too_old(verbose=False, dry_run=False, revisit=False):
    found = []
    deleted = []
    for root, dirs, files in os.walk(settings.FSCACHE_ROOT):
        for file_ in files:
            if file_.endswith(".metadata"):
                continue
            path = os.path.join(root, file_)
            if "index.html" in file_ and not os.stat(path).st_size:
                raise EmptyFSCacheFile(path)
            if os.path.isfile(path + ".metadata"):
                found.append(os.stat(path).st_size)
                seconds = None
                if os.path.isfile(path + ".cache_control"):
                    with open(path + ".cache_control") as seconds_f:
                        seconds = int(seconds_f.read())
                if too_old(path, seconds=seconds):
                    if verbose:
                        print("INVALIDATE", path)
                    if not dry_run:
                        deleted.append(os.stat(path).st_size)
                        deleted = invalidate(path)
                        if verbose:
                            print("\tDELETED", deleted)
                        delete_empty_directory(path)
                        if revisit:
                            revisit_url(path)
                # elif verbose:
                #     print('NOT TOO OLD', path)
        if not files and not os.listdir(root):
            if verbose:
                print("NO FILES IN", root)
            if not dry_run:
                os.rmdir(root)
    if verbose:
        print("Found", len(found), "possible files")
        mb = sum(found) / 1024.0 / 1024.0
        print("Totalling", "%.1f MB" % mb)
        print("Deleted", len(deleted), "files")


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
        and not request.user.is_authenticated
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
