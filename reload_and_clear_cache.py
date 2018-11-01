#!/usr/bin/env python

import os
import shutil
from django.core.wsgi import get_wsgi_application
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "peterbecom.settings")
application = get_wsgi_application()


cache_dir = 'peterbecom-static-content/_FSCACHE'
if os.path.isfile(os.path.join(cache_dir, 'index.html')):
    os.remove(os.path.join(cache_dir, 'index.html'))
plog_cache_dir = os.path.join(cache_dir, 'plog')
if os.path.isdir(plog_cache_dir):
    shutil.rmtree(plog_cache_dir)
    print('Deleted', plog_cache_dir)

from django.core.cache import cache  # noqa
cache.clear()
with open('peterbecom/__init__.py') as f:
    code = f.read()

with open('peterbecom/__init__.py', 'w') as f:
    f.write(code)
