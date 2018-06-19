#!/usr/bin/env python

import re
import time
import os
from collections import defaultdict
import random
from pprint import pprint

from django.core.wsgi import get_wsgi_application
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "peterbecom.settings")
application = get_wsgi_application()

from django.core.cache import cache
urls = cache.get('fancy-urls', {})
for key in urls:
    if 'blogitem-040601-1' in key:
        cache.delete(urls[key])

directory = 'peterbecom-static-content/_FSCACHE/plog/blogitem-040601-1'
import shutil
shutil.rmtree(directory)
