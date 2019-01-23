import os
import tempfile

from django.http import Http404
from peterbecom.settings import *  # noqa


FSCACHE_ROOT = os.path.join(tempfile.gettempdir(), "test-peterbecom-fscache")

ES_INDEX = "test_peterbecom"

REDIS_URL = "redis://localhost:6379/9"

CACHES = {
    "default": {
        "BACKEND": "peterbecom.cache_backends.LockMemCache",
        "LOCATION": "unique-snowflake",
    }
}

ROLLBAR = {
    "enabled": False,
    "access_token": "willneverwork",
    "environment": "production",
    "branch": "master",
    "root": "/tmp",
    "patch_debugview": False,
    "exception_level_filters": [(Http404, "ignored")],
}

OIDC_RP_CLIENT_ID = "bogus"
OIDC_RP_CLIENT_SECRET = "evenmoresecret"

AUTH0_DOMAIN = "peterbecom.auth0.example.com"

OIDC_USER_ENDPOINT = "https://peterbecom.auth0.example.com/userinfooo"

HUEY["always_eager"] = True  # noqa

MINIMALCSS_SERVER_URL = "http://localhost:55555"

MANAGERS = (("Peter", "test@example.com"),)
