import os
import time
from urllib.parse import urljoin, urlparse

import requests

from django.conf import settings
from django.contrib.sites.models import Site


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
    os.remove(fs_path)
    if os.path.isfile(fs_path + ".metadata"):
        os.remove(fs_path + ".metadata")
    if os.path.isfile(fs_path + ".cache_control"):
        os.remove(fs_path + ".cache_control")


def invalidate_by_url(url):
    if not url.startswith("/"):
        url = urlparse(url).path
    fs_path = settings.FSCACHE_ROOT + url + "/index.html"
    if os.path.isfile(fs_path):
        invalidate(fs_path)


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
                        invalidate(path)
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

        not_ends = ("/awspa", "/ping")
        for s in not_ends:
            if request.path.endswith(s):
                return False

        if getattr(request, "_fscache_disable", None):
            # For some reason, the request decided this page should not
            # be FS cached.
            return False

        return True

    return False
