#!/bin/bash

set -e

echo "Making settings/local.py"
cat > peterbecom/settings/local.py <<SETTINGS
from . import base
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'peterbecom',
        'USER': 'user',
        'PASSWORD': 'secret',
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
GEOIP_PATH = base.path('GeoIP2-City-Test.mmdb')
SETTINGS

echo "Run collect static to collect all final static assets."
./manage.py collectstatic --noinput

# Make sure we're running Elasticsearch
curl -v http://localhost:9200/

pytest peterbecom
