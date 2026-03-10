#!/bin/bash

set -e

if [ -f peterbecom/settings/local.py ]; then
  echo "The file peterbecom/settings/local.py already exists. Refusing to override."
  exit 1
fi

echo "Making settings/local.py"
cat > peterbecom/settings/local.py <<SETTINGS
from . import base
import dj_database_url
from decouple import config

DATABASES = {
    "default": config(
        "DATABASE_URL",
        default="postgresql://user:secret@localhost/peterbecom",
        cast=dj_database_url.parse,
    )
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
ALLOWED_HOSTS = ["localhost"]
CSRF_TRUSTED_ORIGINS = ["http://localhost:8000"]
SETTINGS

./bin/run.sh manage.py migrate --no-input


