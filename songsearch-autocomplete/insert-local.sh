#!/bin/bash

set -ex

rm -fr ../peterbecom-static-content/songsearch-autocomplete
aunpack -X ../peterbecom-static-content/ songsearch-autocomplete.zip

export ZOPFLI_PATH=/usr/local/bin/zopfli
./_zopfli.py ../peterbecom-static-content/songsearch-autocomplete/css/*.css
./_zopfli.py ../peterbecom-static-content/songsearch-autocomplete/js/*.js

./_insert.py && \
  ./_zopfli.py ../peterbecom-static-content/_FSCACHE/plog/blogitem-040601-1/index.html
