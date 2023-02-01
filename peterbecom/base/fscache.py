import os
import random
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import backoff
import requests
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.cache import cache
from huey.contrib.djhuey import task

from peterbecom.base.models import CDNPurgeURL
from peterbecom.base.cdn import get_cdn_base_url


class EmptyFSCacheFile(Exception):
    """No fscache written file should ever be 0 bytes."""


def path_to_fs_path(path):
    return settings.FSCACHE_ROOT / path[1:] / "index.html"


def create_parents(fs_path: Path):
    # fs_path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    fs_path.parent.mkdir(parents=True, exist_ok=True)


def too_old(file: Path, seconds: int):
    age = time.time() - file.stat().st_mtime
    return age > seconds


def _invalidate(fs_path: Path):
    assert isinstance(fs_path, Path), type(fs_path)
    deleted = []
    if fs_path.exists():
        attempts = 0
        while attempts < 3:
            try:
                fs_path.unlink()
                deleted.append(fs_path)
                break
            except FileNotFoundError:
                # race condition probably.
                pass

    endings = (".metadata", ".cache_control", ".gz", ".br", ".original")
    for ending in endings:
        fs_path_w = Path(str(fs_path) + ending)
        if fs_path_w.exists():
            attempts = 0
            while attempts < 3:
                try:
                    fs_path_w.unlink()
                    deleted.append(fs_path_w)
                    break
                except FileNotFoundError:
                    # race condition probably.
                    pass

    return deleted


def invalidate_by_url(url, revisit=False):
    if not settings.FSCACHE_ROOT:
        print("Note! FSCACHE_ROOT is not set. Not going to invalidate anything by URL!")
        return
    if not url.startswith("/"):
        url = urlparse(url).path
    if not url.endswith("/"):
        url += "/"

    fs_path = settings.FSCACHE_ROOT / url[1:] / "index.html"
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


def revisit_url(path: Path, verbose=False):
    pathname = str(path.parent.relative_to(settings.FSCACHE_ROOT))
    site = Site.objects.get_current()
    secure = getattr(settings, "FSCACHE_SECURE_SITE", True)
    base_url = secure and "https://" or "http://"
    base_url += site.domain
    url = urljoin(base_url, pathname)
    response = requests.get(url)
    if verbose:
        print("REVISITED", url, response.status_code, response.headers.get("x-cache"))


def invalidate_too_old(
    verbose=False, dry_run=False, revisit=False, check_other_files_age=False
):
    if not settings.FSCACHE_ROOT:
        print("Note! FSCACHE_ROOT is not set. Not going to things that are too old.")
        return

    found = []
    deleted = []

    possibly_empty = set()

    root = settings.FSCACHE_ROOT
    t0 = time.time()
    for file in root.rglob("index.html"):
        if not file.stat().st_size:
            print(f"FSCACHE: Warning! {file} is empty!")
            continue

        if Path(str(file) + ".metadata").exists():
            found.append(file.stat().st_size)
            seconds = None

            # If it ends with .metadata it has to be the index.html
            assert file.name == "index.html", file

            cc_file = Path(str(file) + ".cache_control")
            if cc_file.exists():
                with open(cc_file) as seconds_f:
                    seconds = int(seconds_f.read())

            if seconds is None or too_old(file, seconds):
                if verbose:
                    print(
                        f"FSCACHE: Invalidate {file} {'(dry run)' if dry_run else ''}"
                    )
                if not dry_run:
                    found.append(file.stat().st_size)
                    these_deleted = _invalidate(file)
                    deleted.extend(these_deleted)
                    if verbose:
                        print(f"\tFSCACHE: Deleted {[str(x) for x in these_deleted]}")
                    if revisit:
                        revisit_url(file, verbose=verbose)
                possibly_empty.add(file.parent)
            elif check_other_files_age:
                age_differences = []
                index_html_age = file.stat().st_mtime
                bad_other_files = 0
                for other_file in file.parent.glob("index.html*"):
                    if other_file.name == "index.html":
                        continue
                    other_file_age = other_file.stat().st_mtime
                    age_days = (index_html_age - other_file_age) / 60 / 60 / 24
                    if age_days >= 1:
                        bad_other_files += 1
                    age_differences.append((round(age_days, 1), other_file))

                if bad_other_files:
                    if verbose:
                        print(
                            f"FSCACHE: Invalidate {file} {'(dry run)' if dry_run else ''}"
                        )
                    if not dry_run:
                        found.append(file.stat().st_size)
                        these_deleted = _invalidate(file)
                        deleted.extend(these_deleted)
                        if verbose:
                            print(
                                f"\tFSCACHE: Deleted {[str(x) for x in these_deleted]}"
                            )
                        if revisit:
                            revisit_url(file, verbose=verbose)
                    possibly_empty.add(file.parent)

    for path in possibly_empty:
        # Let's check if there are now 0 files left here in this directory.
        if not list(path.iterdir()):
            if verbose:
                print(f"FSCACHE: No more files in {path}")
            if not dry_run:
                path.rmdir()

    t1 = time.time()

    if verbose:
        print(f"FSCACHE: Found {len(found):,} possible files in {t1 - t0:.1f} seconds")
        mb = sum(found) / 1024.0 / 1024.0
        print(f"FSCACHE: Totalling {mb:.1f} MB")
        print(f"FSCACHE: Deleted {len(deleted):,} files")


def delete_empty_directories(verbose=False, dry_run=False):
    if not settings.FSCACHE_ROOT:
        print("Note! FSCACHE_ROOT is not set. Can't delete empty directories.")
        return

    deleted = []

    def walk(root: Path):
        count_things = 0
        for thing in root.iterdir():
            count_things += 1
            if thing.is_dir():
                walk(thing)

        if not count_things:
            if verbose:
                print(f"{root} is an empty directory")
            if not dry_run:
                root.rmdir()
            deleted.append(root)

    walk(settings.FSCACHE_ROOT)

    if verbose:
        print(f"Deleted {len(deleted)} empty directories")


def cache_request(request, response):
    if not settings.FSCACHE_ROOT:
        print("Note! FSCACHE_ROOT is not set. Not going to cache any requests!")
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

    def visit(root):
        for file in root.iterdir():
            if file.is_dir():
                visit(file)
                continue
            if file.name.endswith(".metadata"):
                continue
            if "index.html" in file.name:
                assert file.stat().st_size, file
                if Path(str(file) + ".metadata").exists() and "/awspa" not in str(file):
                    paths.append((file.stat().st_mtime, file))

    visit(settings.FSCACHE_ROOT)

    # Oldest first
    paths.sort()

    for mtime, file in paths[:max_files]:
        uri = str(file.relative_to(settings.FSCACHE_ROOT))
        if not uri.startswith("/"):
            uri = f"/{uri}"
        uri = re.sub(r"/index\.html$", "", uri)
        if uri == "":
            uri = "/"
        if verbose:
            age_seconds = time.time() - mtime
            if age_seconds > 10000:
                human_age = f"{int(age_seconds / 60 / 60)} hours"
            elif age_seconds > 60:
                human_age = f"{int(age_seconds / 60)} minutes"
            else:
                human_age = f"{age_seconds:.1f} seconds"
            print(f"{uri} last touched {human_age} ago")

        # Update the files modification time so it gets last in the sort order
        # next time.
        os.utime(file, (file.stat().st_atime, time.time()))

        cdn_url = get_cdn_base_url() + uri
        response = _download_cdn_url(cdn_url)
        if response.status_code == 404:
            # # If it can't be viewed on the CDN, it has no business existing as a
            # # fscached filed.
            # # os.remove(path)
            # if verbose:
            #     print(f"Deleted {file!r} because it 404'ed on {cdn_url}")
            continue
        if response.status_code != 200:
            if verbose:
                print(f"{response.status_code} on {cdn_url} :(")
            continue

        if response.headers.get("x-cache") != "HIT":
            if verbose:
                print(
                    f"Wasn't x-cache HIT anyway ({response.headers.get('x-cache')!r}) "
                    f"{cdn_url}"
                )
            continue

        with open(file) as f:
            local_html = f.read()
        remote_html = response.text

        if local_html != remote_html and not dry_run:
            CDNPurgeURL.add(urlparse(cdn_url).path)


def find_missing_compressions(verbose=False, revisit=False):
    deleted = []
    revisits = []

    def visit(root):
        for file in root.iterdir():
            if file.is_dir():
                visit(file)
                continue

            if file.name.endswith(".metadata"):
                continue

            if "index.html" in file.name and file.exists() and not file.stat().st_size:
                print(f"HAD TO DELETE {file} BECAUSE FILE 0 BYTES")
                file.unlink()
                deleted.append(file)
                continue

            if Path(str(file) + ".metadata").exists():
                # If it ends with .metadata it has to be the index.html
                assert file.name == "index.html", file

                br_file = Path(str(file) + ".br")
                gz_file = Path(str(file) + ".gz")
                if not br_file.exists() and "awspa/" not in str(file):
                    if verbose:
                        print(f"{br_file} didn't exist!")
                    file.unlink()
                    deleted.append(file)
                    print(f"HAD TO DELETE {file} BECAUSE .br FILE DOESNT EXIST")
                elif not gz_file.exists() and "awspa/" not in str(file):
                    if verbose:
                        print(f"{gz_file} didn't exist!")
                    file.unlink()
                    deleted.append(file)
                    print(f"HAD TO DELETE {file} BECAUSE .gz FILE DOESNT EXIST")
                else:
                    continue

                if revisit:
                    revisit_url(file, verbose=verbose)
                    revisits.append(file)

    visit(settings.FSCACHE_ROOT)

    if verbose:
        print(f"Deleted {len(deleted):,} files and revisited {len(revisits):,} paths")


def clean_disfunctional_folders(verbose=False, revisit=False):
    deleted = []
    revisits = []

    def visit(root):
        index_html_file = None
        metadata_files = []
        for file in root.iterdir():
            if file.is_dir():
                visit(file)
                continue

            if file.name in (
                "index.html.metadata",
                "index.html.original",
                "index.html.cache_control",
            ):
                metadata_files.append(file)
                continue

            if file.name == "index.html":
                index_html_file = file
                continue

        # If this happens you have a folder that contains files like
        #  * index.html.metadata
        #  * index.html.cache_control
        #  * index.html.original
        # But no file like:
        #  * index.html
        # That's not good!
        if not index_html_file and metadata_files:
            # Delete all the metadata files and possibly trigger a revisit
            deleted.extend(metadata_files)
            [x.unlink() for x in metadata_files]
            if revisit:
                revisit_url(root, verbose=verbose)
                revisits.append(root)

    visit(settings.FSCACHE_ROOT)

    if verbose:
        print(
            f"Deleted {len(deleted):,} disfunctional files "
            f"and revisited {len(revisits):,} paths"
        )
