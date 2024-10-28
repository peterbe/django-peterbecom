#!/bin/bash

set -e

if [ -f peterbecom/settings/local.py ]; then
  echo "The file peterbecom/settings/local.py already exists. Refusing to override."
  exit 1
fi

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
OIDC_RP_CLIENT_ID = 'secret'
OIDC_RP_CLIENT_SECRET = 'secreter'
ROLLBAR = {
    "enabled": False,  # NOTE!
}
USE_ES_SYNONYM_FILE_NAME = False
SETTINGS

# Make sure we're running Elasticsearch
curl -v http://localhost:9200/

# uv run pytest peterbecom
./bin/run.sh test
