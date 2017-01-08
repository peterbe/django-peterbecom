# -*- coding: utf-8 -*-

import os

from .bundles import PIPELINE_CSS, PIPELINE_JS


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def path(*x):
    return os.path.join(BASE_DIR, *x)


DEBUG = False

ADMINS = (
    # ('Your Name', 'your_email@example.com'),
)

MANAGERS = ADMINS

TEST_RUNNER = 'django.test.runner.DiscoverRunner'

SITE_ID = 1

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.',
        'NAME': '',
        'USER': '',
        'PASSWORD': '',
        'HOST': '',
        'PORT': '',
    }
}

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'America/Chicago'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

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
MEDIA_ROOT = ''

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_URL = '/'

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"
# STATIC_ROOT = ''
STATIC_ROOT = path('static')

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = '/static/'

# Additional locations of static files
# STATICFILES_DIRS = (
#     # Put strings here, like "/home/html/static" or "C:/www/django/static".
#     # Always use forward slashes, even on Windows.
#     # Don't forget to use absolute paths, not relative paths.
#     path('static'),
# )

STATICFILES_STORAGE = 'pipeline.storage.PipelineCachedStorage'

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'pipeline.finders.PipelineFinder',
)

# Make this unique, and don't share it with anybody.
SECRET_KEY = ''  # set in local settings


MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    # Important that this is last
    'peterbecom.base.middleware.FSCacheMiddleware',
)

ROOT_URLCONF = 'peterbecom.urls'

AUTHENTICATION_BACKENDS = (
    'peterbecom.base.auth_backend.AuthBackend',
    'django.contrib.auth.backends.ModelBackend',
)

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = 'peterbecom.wsgi.application'


_CONTEXT_PROCESSORS = (
    'django.contrib.auth.context_processors.auth',
    'django.template.context_processors.debug',
    'django.template.context_processors.media',
    'django.template.context_processors.static',
    'django.template.context_processors.tz',
    'django.template.context_processors.request',
    'peterbecom.homepage.context_processors.context',
    'django_auth0.context_processors.auth0',
)

TEMPLATES = [
    {
        'BACKEND': 'django_jinja.backend.Jinja2',
        'APP_DIRS': True,
        'OPTIONS': {
            # Use jinja2/ for jinja templates
            'app_dirname': 'jinja2',
            # Don't figure out which template loader to use based on
            # file extension
            'match_extension': '',
            # 'newstyle_gettext': True,
            'context_processors': _CONTEXT_PROCESSORS,
            'debug': False,
            'undefined': 'jinja2.Undefined',
            'extensions': [
                'jinja2.ext.do',
                'jinja2.ext.loopcontrols',
                'jinja2.ext.with_',
                'jinja2.ext.i18n',  # needed to avoid errors in django_jinja
                'jinja2.ext.autoescape',
                'django_jinja.builtins.extensions.CsrfExtension',
                'django_jinja.builtins.extensions.StaticFilesExtension',
                'django_jinja.builtins.extensions.DjangoFiltersExtension',
                'pipeline.jinja2.PipelineExtension',
            ],
            'globals': {
            }
        }
    },
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],  # what does this do?!
        'APP_DIRS': True,
        'OPTIONS': {
            'debug': False,
            'context_processors': _CONTEXT_PROCESSORS,
        }
    },
]

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.staticfiles',
    # 'django_celery_results',
    # 'django.contrib.admin',
    # 'kombu.transport.django',

    'semanticuiform',
    'sorl.thumbnail',
    'django_auth0',

    'peterbecom.base',
    'peterbecom.plog',
    'peterbecom.homepage',
    'peterbecom.nodomains',
    'peterbecom.ajaxornot',
    'peterbecom.localvsxhr',
    'peterbecom.cdnthis',
    'peterbecom.podcasttime',
    'fancy_cache',
    'pipeline',
    'django_jinja',
)

# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error when DEBUG=False.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler'
        }
    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
    }
}


def JINJA_CONFIG():
    config = {
        'extensions': [
            'jinja2.ext.do',
            'jinja2.ext.with_',
            'jinja2.ext.loopcontrols',
            'pipeline.templatetags.ext.PipelineExtension',
        ],
        'finalize': lambda x: x if x is not None else '',
    }
    return config


PIPELINE = {
    'STYLESHEETS': PIPELINE_CSS,
    'JAVASCRIPT': PIPELINE_JS,
    'JS_COMPRESSOR': 'pipeline.compressors.uglifyjs.UglifyJSCompressor',
    'UGLIFYJS_BINARY': path('node_modules/.bin/uglifyjs'),
    'UGLIFYJS_ARGUMENTS': '--mangle',
    'CSS_COMPRESSOR': 'pipeline.compressors.NoopCompressor',
    'DISABLE_WRAPPER': True,
    # The pipeline.jinja2.PipelineExtension extension doesn't support
    # automatically rendering any potentional compilation errors into
    # the rendered HTML, so just let it raise plain python exceptions.
    'SHOW_ERRORS_INLINE': False,
}


CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.memcached.MemcachedCache',
        'KEY_PREFIX': 'peterbecom',
        'TIMEOUT': 5 * 60,
        'LOCATION': '127.0.0.1:11211'
    }
}

# CELERY_RESULT_BACKEND = 'django-db'
# BROKER_URL = "django://"
# BROKER_CONNECTION_TIMEOUT = 0.1
# CELERYD_CONCURRENCY = 2
# CELERY_ALWAYS_EAGER = False
# CELERY_IGNORE_RESULT = True

SESSION_COOKIE_HTTPONLY = True
SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'
SESSION_COOKIE_AGE = 60 * 60 * 24 * 365  # 1 year


UPLOAD_FILE_DIR = path('peterbecom-static-content')

LOGIN_URL = '/admin/'

INBOUND_EMAIL_ADDRESS = 'setup@yourown.com'

FANCY_REMEMBER_ALL_URLS = True
FANCY_REMEMBER_STATS_ALL_URLS = True

PHANTOMJS_PATH = 'phantomjs'

AUTOCOMPETER_AUTH_KEY = ''

CDNTHIS_DOMAINS = {}

PINGDOM_RUM_ID = None


# Because https://pypi.python.org/pypi/pygments-lexer-babylon isn't
# particularly flexible. You can only set this via an environment variable.
os.environ['PYGMENTS_NODE_COMMAND'] = 'node'

THUMBNAIL_BACKEND = 'optisorl.backend.OptimizingThumbnailBackend'

AUTH0_DOMAIN = 'peterbecom.auth0.com'
AUTH0_CLIENT_ID = 'YOU_CLIENT_ID'
AUTH0_SECRET = 'YOUR_SECRET'
AUTH0_CALLBACK_URL = 'https://www.peterbe.com/auth/callback'
AUTH0_SUCCESS_URL = '/?logged=in'

AUTH_SIGNOUT_URL = 'https://www.peterbe.com/?logged=out'


# A path to where Nginx will look for files first
FSCACHE_ROOT = path('peterbecom-static-content/_FSCACHE')
assert not FSCACHE_ROOT.endswith('/')
