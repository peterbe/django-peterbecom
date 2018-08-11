#!/bin/bash

set -e

rm -fr ../peterbecom-static-content/songsearch-autocomplete
aunpack -X ../peterbecom-static-content/ songsearch-autocomplete.zip

export ZOPFLI_PATH=/usr/local/bin/zopfli
./_zopfli.py ../peterbecom-static-content/songsearch-autocomplete/css/*.css
./_zopfli.py ../peterbecom-static-content/songsearch-autocomplete/js/*.js

./_insert.py && \
  ./_zopfli.py ../peterbecom-static-content/_FSCACHE/plog/blogitem-040601-1/index.html


ls -ltr ../peterbecom-static-content/_FSCACHE/plog/blogitem-040601-1/
if [ -f ../peterbecom-static-content/_FSCACHE/plog/blogitem-040601-1/index.html.gz ]; then
   if [ ../peterbecom-static-content/_FSCACHE/plog/blogitem-040601-1/index.html.gz -ot ../peterbecom-static-content/_FSCACHE/plog/blogitem-040601-1/index.html ]; then
        echo "OH NO! index.html is older than index.html.gz!!!"
        rm ../peterbecom-static-content/_FSCACHE/plog/blogitem-040601-1/index.html.gz
        echo "Generating a new index.html.gz"
        ./_zopfli.py ../peterbecom-static-content/_FSCACHE/plog/blogitem-040601-1/index.html
    else
        echo "All is well."
    fi
else
    echo "The file index.html.gz doesn't even exist!!"
fi
