#!/bin/bash

set -e
if [ "$1" == "--help" ]; then
  bunx wait-port --help
else
  bunx wait-port localhost:6432 -t 30000
fi
