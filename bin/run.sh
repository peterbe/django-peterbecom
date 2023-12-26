#!/usr/bin/env bash
set -eo pipefail


usage() {
  echo "usage: ./bin/run.sh web|web-dev|worker|test|bash|superuser"
  exit 1
}

wait_for() {
  tries=0
  echo "Waiting for $1 to listen on $2..."
  while true; do
    [[ $tries -lt $TRIES ]] || return
    (echo > /dev/tcp/$1/$2) >/dev/null 2>&1
    result=
    [[ $? -eq 0 ]] && return
    sleep $SLEEP
    tries=$((tries + 1))
  done
}

[ $# -lt 1 ] && usage

# Only wait for backend services in development
# http://stackoverflow.com/a/13864829
# For example, bin/test.sh sets 'DEVELOPMENT' to something
# [ ! -z ${DEVELOPMENT+check} ] && wait_for db 5432 && wait_for elasticsearch 9200 && wait_for redis 6379
# [ ! -z ${DEVELOPMENT+check} ] && wait_for db 5432 && wait_for elasticsearch 9200 && wait_for redis 6379


case $1 in
  web)
    # echo "STARTING WEB-DEV"
    #python manage.py clear-django-cache
    python manage.py migrate --noinput
    # export PYTHONWARNINGS=d
    exec python manage.py runserver 0.0.0.0:8000
    ;;
  superuser)
    exec python manage.py superuser "${@:2}"
    ;;
  test)
    exec python ./manage.py test
    ;;
  bash)
    # echo "For high-speed test development, run: pip install pytest-watch"
    exec "$@"
    ;;
  *)
    exec "$@"
    ;;
esac
