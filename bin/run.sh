#!/usr/bin/env bash
set -eo pipefail

# default variables
: "${PORT:=8000}"
# How many Gunicorn workers should you use?
# According to https://docs.gunicorn.org/en/stable/design.html#how-many-workers
# the formula is simple: (2 x $num_cores) + 1
# Leave it small if you have no way of knowing how many CPU cores you
# have, otherwise apply the formula.
: "${WORKERS:=2}"

usage() {
  echo "usage: ./bin/run.sh web|web-dev|worker|test|bash|huey"
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

setup_python() {
  source .venv/bin/activate

  # Needed for importing cairocffi
  export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib  # Silicon?
  export DYLD_FALLBACK_LIBRARY_PATH=/usr/local/lib  # Intel?
  export DYLD_FALLBACK_LIBRARY_PATH=`brew --prefix`/lib  # Both?

  # python -c 'import django; print(django.get_version())'
  # python -c 'import sys; print(sys.base_prefix)'
  # python -c 'import cairocffi; print(cairocffi.version)'

}


case $1 in
  web-dev)
    echo "STARTING WEB-DEV  (:${PORT})"
    setup_python
    python manage.py migrate --noinput
    # export PYTHONWARNINGS=d
    exec python manage.py runserver 0.0.0.0:${PORT}
    ;;
  web)
    echo "STARTING WEB (with gunicorn) (:${PORT})"
    setup_python
    python manage.py migrate --noinput
    # export PYTHONWARNINGS=d
    gunicorn wsgi -w ${WORKERS} -b 0.0.0.0:${PORT} --access-logfile=-
    ;;
  test)
    setup_python
    shift # Shift all arguments to the left (drop $1)
    pytest $@
    ;;
  test-with-coverage)
    setup_python
    pytest --cov=peterbecom --cov-report=html
    ;;
  test-with-coverage-xml)
    setup_python
    pytest --cov=peterbecom --cov-report=xml:coverage.xml
    ;;
  huey)
    setup_python
    python manage.py run_huey --flush-locks --huey-verbose
    ;;
  bash)
    # echo "For high-speed test development, run: pip install pytest-watch"
    exec "$@"
    ;;
  *)
    exec "$@"
    ;;
esac
