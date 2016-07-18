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


def invalidate_too_old(verbose=False):
    for root, dirs, files in os.walk(settings.FSCACHE_ROOT):
        for file_ in files:
            if file_.endswith('.metadata'):
                continue
            path = os.path.join(root, file_)
            if os.path.isfile(path + '.metadata'):
                if too_old(path):
                    if verbose:
                        print "INVALIDATE", path
                    invalidate(path)
