import os
import tempfile

from django.http import Http404
from peterbecom.settings import *  # noqa

CELERY_ALWAYS_EAGER = True
CELERY_EAGER_PROPAGATES_EXCEPTIONS = True


FSCACHE_ROOT = os.path.join(tempfile.gettempdir(), "test-peterbecom-fscache")

ES_INDEX = "test_peterbecom"

REDIS_URL = "redis://localhost:6379/9"


ROLLBAR = {
    "enabled": False,
    "access_token": "willneverwork",
    "environment": "production",
    "branch": "master",
    "root": "/tmp",
    "patch_debugview": False,
    "exception_level_filters": [(Http404, "ignored")],
}
