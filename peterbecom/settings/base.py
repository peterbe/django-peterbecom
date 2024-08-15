from pathlib import Path

import dj_database_url
from decouple import config

BASE_DIR = Path(__file__).parent.parent.parent


def path(*x):
    # Use str() here because Python 3.5's open() builtin can't take a PosixPath.
    return str(BASE_DIR.joinpath(*x))


DEBUG = False

ADMINS = (
    # ('Your Name', 'your_email@example.com'),
)

MANAGERS = ADMINS

TEST_RUNNER = "django.test.runner.DiscoverRunner"

SITE_ID = 1

DATABASES = {
    "default": config(
        "DATABASE_URL",
        default="postgresql://peterbe@localhost/peterbecom",
        cast=dj_database_url.parse,
    )
}

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = "America/Chicago"

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = "en-us"

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = False

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale.
USE_L10N = True

# If you set this to False, Django will not use timezone-aware datetimes.
USE_TZ = True

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
MEDIA_ROOT = ""

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_URL = "/"

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"
# STATIC_ROOT = ''
# STATIC_ROOT = path("static")
STATIC_ROOT = BASE_DIR / "static"


# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = "/static/"

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
)

# Make this unique, and don't share it with anybody.
SECRET_KEY = ""  # set in local settings

MIDDLEWARE = (
    "django.middleware.common.CommonMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "rollbar.contrib.django.middleware.RollbarNotifierMiddleware",
    "peterbecom.api.middleware.AuthenticationMiddleware",
    "peterbecom.base.middleware.NoNewlineRequestPaths",
    # Important that this is last
    "peterbecom.base.middleware.StatsMiddleware",
    # "querycount.middleware.QueryCountMiddleware",
)

ROOT_URLCONF = "peterbecom.urls"

AUTHENTICATION_BACKENDS = (
    "peterbecom.base.auth.AuthenticationBackend",
    "django.contrib.auth.backends.ModelBackend",
)
OIDC_RP_SCOPES = "openid email picture profile"

OIDC_OP_AUTHORIZATION_ENDPOINT = "https://peterbecom.auth0.com/authorize"
OIDC_OP_TOKEN_ENDPOINT = "https://peterbecom.auth0.com/oauth/token"
OIDC_OP_USER_ENDPOINT = "https://peterbecom.auth0.com/userinfo"

LOGIN_REDIRECT_URL = "/?login=1"
LOGOUT_REDIRECT_URL = "/?loggedout=1"

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = "wsgi.application"


_CONTEXT_PROCESSORS = (
    "django.contrib.auth.context_processors.auth",
    "django.template.context_processors.debug",
    "django.template.context_processors.media",
    "django.template.context_processors.static",
    "django.template.context_processors.tz",
    "django.template.context_processors.request",
)

TEMPLATES = [
    {
        "BACKEND": "django_jinja.backend.Jinja2",
        "APP_DIRS": True,
        "OPTIONS": {
            # Use jinja2/ for jinja templates
            "app_dirname": "jinja2",
            # Don't figure out which template loader to use based on
            # file extension
            "match_extension": "",
            # 'newstyle_gettext': True,
            "context_processors": _CONTEXT_PROCESSORS,
            "debug": False,
            "undefined": "jinja2.Undefined",
            "extensions": [
                "jinja2.ext.do",
                "jinja2.ext.loopcontrols",
                "jinja2.ext.with_",
                "jinja2.ext.i18n",  # needed to avoid errors in django_jinja
                "jinja2.ext.autoescape",
                "django_jinja.builtins.extensions.CsrfExtension",
                "django_jinja.builtins.extensions.StaticFilesExtension",
                "django_jinja.builtins.extensions.DjangoFiltersExtension",
            ],
            "globals": {},
        },
    },
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],  # what does this do?!
        "APP_DIRS": True,
        "OPTIONS": {"debug": False, "context_processors": _CONTEXT_PROCESSORS},
    },
]

INSTALLED_APPS = (
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "mozilla_django_oidc",
    "sorl.thumbnail",
    "peterbecom.base",
    "peterbecom.plog",
    "peterbecom.api",
    "peterbecom.publicapi",
    "peterbecom.homepage",
    "peterbecom.chiveproxy",
    "peterbecom.minimalcss",
    "peterbecom.bayes",
    "django_jinja",
    "huey.contrib.djhuey",
)

# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error when DEBUG=False.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "require_debug_false": {"()": "django.utils.log.RequireDebugFalse"},
        "require_debug_true": {"()": "django.utils.log.RequireDebugTrue"},
    },
    "handlers": {"console": {"level": "INFO", "class": "logging.StreamHandler"}},
    "loggers": {
        "django.security.csrf": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": True,
        },
        "huey": {"handlers": ["console"], "level": "INFO", "propagate": True},
    },
}


def JINJA_CONFIG():
    config = {
        "extensions": [
            "jinja2.ext.do",
            "jinja2.ext.with_",
            "jinja2.ext.loopcontrols",
        ],
        "finalize": lambda x: x if x is not None else "",
    }
    return config


# REDIS_URL = 'redis://redis:6379/0'
REDIS_URL = config("REDIS_URL", "redis://localhost:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",  # noqa
            # Not using the msgpack serializer because msgpack can't
            # serialize a HttpResponse object.
        },
    }
}


SESSION_COOKIE_HTTPONLY = True
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 365  # 1 year


UPLOAD_FILE_DIR = path("peterbecom-static-content")

LOGIN_URL = "/admin/"

INBOUND_EMAIL_ADDRESS = "setup@yourown.com"

FANCY_REMEMBER_ALL_URLS = True
FANCY_REMEMBER_STATS_ALL_URLS = True

CDNTHIS_DOMAINS = {}

PINGDOM_RUM_ID = None

# Number of blog posts to show on the homepage, per page.
# Equally used when filtered by category.
HOMEPAGE_BATCH_SIZE = 6

THUMBNAIL_BACKEND = "optisorl.backend.OptimizingThumbnailBackend"

AUTH0_DOMAIN = "peterbecom.auth0.com"
AUTH0_CLIENT_ID = "YOU_CLIENT_ID"
AUTH0_SECRET = "YOUR_SECRET"
AUTH0_CALLBACK_URL = "https://www.peterbe.com/auth/callback"
AUTH0_SUCCESS_URL = "/?logged=in"

AUTH_SIGNOUT_URL = "https://www.peterbe.com/?logged=out"


# CSRF_FAILURE_VIEW = "peterbecom.base.views.csrf_failure"

# ElasticSearch

# ES_BLOG_ITEM_INDEX = config("ES_BLOG_ITEM_INDEX", default="blog_item")
# ES_BLOG_COMMENT_INDEX = config("ES_BLOG_COMMENT_INDEX", default="blog_comment")
ES_BLOG_ITEM_INDEX = "blog_items"
ES_BLOG_COMMENT_INDEX = "blog_comments"
ES_SEARCH_TERM_INDEX = "search_terms"

_ES_INDEX_SETTINGS = {"number_of_shards": 1, "number_of_replicas": 0}
ES_BLOG_ITEM_INDEX_SETTINGS = _ES_INDEX_SETTINGS
ES_BLOG_COMMENT_INDEX_SETTINGS = _ES_INDEX_SETTINGS
ES_SEARCH_TERM_INDEX_SETTINGS = _ES_INDEX_SETTINGS

ES_CONNECTIONS = {"default": {"hosts": ["localhost:9200"]}}

LATEST_PODCAST_CUTOFF_DAYS = 300

MAX_RECENT_COMMENTS = 85

MAX_BLOGCOMMENT_PAGES = 20

MOZJPEG_PATH = "mozjpeg"
GUETZLI_PATH = "guetzli"
PNGQUANT_PATH = "pngquant"

LOGIN_URL = "/signin/"

MINIMALCSS_SERVER_URL = "http://localhost:5555"
MINIMALCSS_TIMEOUT_SECONDS = 12.0  # Most seem to take about 2-4 seconds in production

ENABLE_CLIENT_SIDE_ROLLBAR = False


HTML_MINIFIER_PATH = path("node_modules/.bin/html-minifier")
HTML_MINIFIER_TIMEOUT_SECONDS = 2.0

# These domains don't need the `rel="nofollow"` attribute when linkified.
NOFOLLOW_EXCEPTIONS = ("peterbe.com", "www.peterbe.com", "songsear.ch")


PLOG_GOOD_STRINGS = (
    "I've been looking",
    "anyone know this song",
    "these lyrics",
    "to find a song",
    "find this song",
    "The lyrics go",
    "looking for a song",
    "This is a song I",
)

PLOG_BAD_STRINGS = ("@",)


HUEY = {
    "name": DATABASES["default"]["NAME"],  # Use db name for huey.
    "results": False,  # Store return values of tasks.
    "store_none": False,  # If a task returns None, do not save to results.
    "immediate": False,
    "huey_class": "huey.RedisHuey",  # Use path to redis huey by default,
    "connection": {
        "read_timeout": 1,  # If not polling (blocking pop), use timeout.
        "url": REDIS_URL,  # Allow Redis config via a DSN.
    },
    "consumer": {
        "workers": 4,
        "worker_type": "thread",
        "initial_delay": 0.1,  # Smallest polling interval, same as -d.
        "backoff": 1.15,  # Exponential backoff using this rate, -b.
        "max_delay": 10.0,  # Max possible polling interval, -m.
        "utc": True,  # Treat ETAs and schedules as UTC datetimes.
        "scheduler_interval": 1,  # Check schedule every second, -s.
        "periodic": True,  # Enable crontab feature.
        "check_worker_health": True,  # Enable worker health checks.
        "health_check_interval": 2,  # Check worker health every second.
    },
}

OIDC_USER_ENDPOINT = "https://peterbecom.auth0.com/userinfo"

ADMINUI_COMMENTS_BATCH_SIZE = 20

GEOIP_PATH = path("GeoLite2-City.mmdb")

DELAY_SENDING_BLOGCOMMENT_REPLY_SECONDS = 60

KEYCDN_HOST = "www.peterbe.com"
# https://app.keycdn.com/zones/index
KEYCDN_ZONE_URL = "www-2916.kxcdn.com"

# This means, it will use the Nginx way instead.
# Essential when using Nginx proxy_cache for local development.
# USE_NGINX_BYPASS = False
# When Huey gets a request to purge URLs and you have enabled 'USE_NGINX_BYPASS'
# it might need a base_url if the request URL is just the path.
# NGINX_BYPASS_BASEURL = None

# E.g. /var/cache/nginx-cache/next
# NGINX_CACHE_DIRECTORY = None

PURGE_URL = None
PURGE_SECRET = None

SEND_KEYCDN_PURGES = True

ORIGIN_TO_HOST = {"www-origin.peterbe.com": "www.peterbe.com"}

FAKE_BLOG_COMMENT_IP_ADDRESS = False

# Override in local
GOOGLE_MAPS_API_KEY = None

# Comments from these people should go straight to trash
TRASH_COMMENT_COMBINATIONS = [
    # Example...
    # {"name": "Foo", "email": ""}
    # {"user_agent": re.compile(r'foo'), "ip_address": "123.456.789.12"},
]

QUERYCOUNT = {
    "THRESHOLDS": {
        "MEDIUM": 50,
        "HIGH": 200,
        "MIN_TIME_TO_LOG": 0,
        "MIN_QUERY_COUNT_TO_LOG": 0,
    },
    "IGNORE_REQUEST_PATTERNS": [r"^/api/v0/cdn/purge/urls/count"],
    "IGNORE_SQL_PATTERNS": [],
    "DISPLAY_DUPLICATES": None,
    "RESPONSE_HEADER": "X-DjangoQueryCount-Count",
}

QUICKMETRICS_API_KEY = None

# When asking the CDNPurgeURL model for the next URLs to send to CDN purgning.
# This number limits the batch size.
CDN_MAX_PURGE_URLS = 15


# These parameters are very important and very tricky.
# How you use them matters in terms of how you combine them.
# If you use `BOOST_MODE=sum` the scoring is computed by:
# `score = matchness_score + popularity * popularity_factor`
# Since the popularity is always a number between 1 and 0, if a document
# has virtually 0 (0.0000001) in popularity, the "matchess score" will dominate.
# If you, however `BOOST_MODE=sum` but `POPULARITY_FACTOR=10000` that popularity
# will start to influence more.
DEFAULT_POPULARITY_FACTOR = 10.0
DEFAULT_BOOST_MODE = "sum"

# Avoid DB reads and writes as much as possible
DB_MAINTENANCE_MODE = False

SEND_PULSE_MESSAGES = True

SYNONYM_FILE_NAME = config("SYNONYM_FILE_NAME", default="peterbecom.synonyms")
USE_ES_SYNONYM_FILE_NAME = config("USE_ES_SYNONYM_FILE_NAME", default=True, cast=bool)

# Every 404 is captured and counted in an upsert query. Each time,
# the 'last_seen' date is updated.
# Some records that we haven't seen for a long long time are not worth
# worry about. And it just fills up the database unnecessarily.
# This defines, how many days ago something in CatchallURLs is considered
# too old and can be deleted.
MIN_RARELY_SEEN_CATCHALL_DAYS = 30

HYLITE_DIRECTORY = None
HYLITE_COMMAND = "bunx hylite"

LYRICS_REMOTE = "https://songsear.ch"
