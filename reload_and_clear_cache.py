#!/usr/bin/env python

import os
import shutil
from django.core.wsgi import get_wsgi_application
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "peterbecom.settings")
application = get_wsgi_application()


cache_dir = 'peterbecom-static-content/_FSCACHE/plog'
if os.path.isdir(cache_dir):
    shutil.rmtree(cache_dir)
    print('Deleted', cache_dir)

from django.core.cache import cache  # noqa
cache.clear()
with open('peterbecom/__init__.py') as f:
    code = f.read()

with open('peterbecom/__init__.py', 'w') as f:
    f.write(code)
