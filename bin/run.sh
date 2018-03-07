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
    python manage.py collectstatic --noinput
    python manage.py fscache -v 2  # deletes old FS cached files
    python manage.py migrate --noinput
    exec python manage.py runserver 0.0.0.0:8000
    ;;
  worker)
    # echo "STARTING WORKER WITHOUT PURGE"
    celery -A peterbecom worker -l info
    ;;
  worker-purge)
    # Start worker but first purge ALL old stale tasks.
    # Only useful in local development where you might have accidentally
    # started waaaay too make background tasks when debugging something.
    # Or perhaps the jobs belong to the wrong branch as you stop/checkout/start
    # the docker container.
    # echo "STARTING WORKER WITH PURGE"
    celery -A peterbecom worker -l info --purge
    ;;
  superuser)
    exec python manage.py superuser "${@:2}"
    ;;
  test)
    python manage.py collectstatic --noinput
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
