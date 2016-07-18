import os
import time
import re

from django.conf import settings


file_extension_re = re.compile('\w+\.\w{2,4}$')


def path_to_fs_path(path):
    if path.endswith('/') or not file_extension_re.findall(path):
        fs_path = settings.FSCACHE_ROOT
        for directory in path.split('/'):
            if directory:
                fs_path += '/' + directory
            if not os.path.isdir(fs_path):
                os.mkdir(fs_path)
                os.chmod(fs_path, 0755)
        return fs_path + '/index.html'


def too_old(fs_path):
    cache_seconds = 60 * 60 * 24  # default
    uri = fs_path.replace(settings.FSCACHE_ROOT, '')
    if uri.startswith('/plog'):
        cache_seconds = 60 * 60 * 24 * 7

    age = time.time() - os.stat(fs_path).st_mtime
    return age > cache_seconds


def invalidate(fs_path):
    os.remove(fs_path)
    if os.path.isfile(fs_path + '.metadata'):
        os.remove(fs_path + '.metadata')


def invalidate_too_old(verbose=False, dry_run=False):
    found = []
    deleted = []
    for root, dirs, files in os.walk(settings.FSCACHE_ROOT):
        for file_ in files:
            if file_.endswith('.metadata'):
                continue
            path = os.path.join(root, file_)
            if os.path.isfile(path + '.metadata'):
                found.append(os.stat(path).st_size)
                if too_old(path):
                    if verbose:
                        print "INVALIDATE", path
                    if not dry_run:
                        invalidate(path)
                        deleted.append(os.stat(path).st_size)
                        # delete_empty_directory(path)
    if verbose:
        print "Found", len(found), "possible files"
        mb = sum(found) / 1024.0 / 1024.0
        print "Totalling", "%.1f MB" % mb
        print "Deleted", len(deleted), "files"


def cache_request(request, response):
    if not settings.FSCACHE_ROOT:
        # bail if it hasn't been set up
        return False
    if (
        request.method == 'GET' and
        request.path != '/' and
        response.status_code == 200 and
        not request.META.get('QUERY_STRING') and
        not request.user.is_authenticated() and
        # XXX TODO: Support JSON and xml
        'text/html' in response['Content-Type']
    ):
        # let's iterate through some exceptions
        not_starts = (
            '/stats/',
            '/search',
            '/ajaxornot',
            '/localvsxhr',
            '/auth',
            '/podcasttime',
            '/nodomain',
        )
        for s in not_starts:
            if request.path.startswith(s):
                return False

        return True

    return False
