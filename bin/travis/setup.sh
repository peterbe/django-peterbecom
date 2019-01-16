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
HMAC_KEYS = {'some': 'thing'}
SECRET_KEY = 'something'
CACHES = {
    'default': {
        'BACKEND': 'peterbecom.cache_backends.LockMemCache',
        'LOCATION': 'unique-snowflake'
    }
}
SETTINGS

echo "Version of babel?"
./node_modules/.bin/babel --version

echo "Run collect static to collect all final static assets."
./manage.py collectstatic --noinput
