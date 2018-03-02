#!/usr/bin/env bash
set -eo pipefail


usage() {
  echo "usage: ./bin/run.sh start"
  exit 1
}

case $1 in
  start)
    yarn run start
    ;;
  *)
    exec "$@"
    ;;
esac
