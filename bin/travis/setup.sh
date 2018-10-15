#!/bin/bash
# pwd is the git repo.
set -e

echo "Making settings/local.py"
cat > peterbecom/settings/local.py <<SETTINGS
from . import base
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'peterbecom',
        'USER': 'travis',
        'PASSWORD': '',
        'HOST': 'localhost',
        'PORT': '',
    },
}
ES_CONNECTIONS = {
    'default': {
        'hosts': ['localhost:9200'],
    },
}
REDIS_URL = 'redis://localhost:6379/0'
CELERY_BROKER_URL = REDIS_URL
HMAC_KEYS = {'some': 'thing'}
SECRET_KEY = 'something'
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake'
    }
}
CELERY_TASK_ALWAYS_EAGER = True
SETTINGS

echo "Installing the node packages"
yarn
yarn --version

./manage.py collectstatic --noinput
