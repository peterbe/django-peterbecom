import os

from django.http import Http404

from peterbecom.settings import *  # noqa

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

# OIDC_RP_CLIENT_ID = "bogus"
# OIDC_RP_CLIENT_SECRET = "evenmoresecret"

AUTH0_DOMAIN = "peterbecom.auth0.example.com"

OIDC_USER_ENDPOINT = "https://peterbecom.auth0.example.com/userinfooo"

HUEY["immediate"] = True  # noqa

MINIMALCSS_SERVER_URL = "http://localhost:55555"

MANAGERS = (("Peter", "test@example.com"),)

SPAM_URL_PATTERNS = ["http://mustbesomething.example.com"]

# From https://github.com/maxmind/MaxMind-DB/tree/master/test-data
GEOIP_PATH = path("GeoIP2-City-Test.mmdb")  # noqa
assert os.path.isfile(GEOIP_PATH), GEOIP_PATH


# Set this explicitly on in individual tests
TRASH_COMMENT_COMBINATIONS = []

# Because ideally no WebSocket should be listening when running tests.
SEND_PULSE_MESSAGES = False

RUNNING_TESTS = True
