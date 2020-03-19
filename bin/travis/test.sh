#!/bin/bash
# pwd is the git repo.
set -e

# Make sure we're running Elasticsearch
curl -v http://localhost:9200/

pytest peterbecom


# Go into the adminui directory and expect to be able to run yarn run build
pushd adminui
yarn run build

# If the webpack stuff didn't work, it would only have created...
#
#   - 2.fdb5cd4e.chunk.js(.map)
#   - main.d8a9c6c6.chunk.js(.map)
#   - runtime-main.62a7d8f7.js(.map)
#
# If the webpack stuff did work there'll be lots of other files with higher
# numbers beyond just 2.
ls -l build/static/js/3.*


popd
