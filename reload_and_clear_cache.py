#!/usr/bin/env python

import os
from django.core.wsgi import get_wsgi_application
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "peterbecom.settings")
application = get_wsgi_application()

from django.core.cache import cache  # noqa
cache.clear()
with open('peterbecom/__init__.py') as f:
    code = f.read()

with open('peterbecom/__init__.py', 'w') as f:
    f.write(code)
