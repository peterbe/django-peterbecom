#!/bin/bash
# pwd is the git repo.
set -e

# Make sure we're running ES 5
curl -v http://localhost:9200/

pytest peterbecom
