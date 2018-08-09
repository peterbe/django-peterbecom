#!/bin/bash

set -ex

LOGFILE=/var/log/django/insert-songsearch-autocomplete.log
exec >> $LOGFILE 2>&1

cd /home/django/django-peterbecom/songsearch-autocomplete
rm -fr ../peterbecom-static-content/songsearch-autocomplete
aunpack -X ../peterbecom-static-content/ songsearch-autocomplete.zip

./_zopfli.py ../peterbecom-static-content/songsearch-autocomplete/css/*.css
./_zopfli.py ../peterbecom-static-content/songsearch-autocomplete/js/*.js

./_insert.py && \
  ./_zopfli.py ../peterbecom-static-content/_FSCACHE/plog/blogitem-040601-1/index.html


# Temporary stuff
ls -ltr ../peterbecom-static-content/_FSCACHE/plog/blogitem-040601-1/
if [ -f ../peterbecom-static-content/_FSCACHE/plog/blogitem-040601-1/index.html.gz ]; then
   if [ ../peterbecom-static-content/_FSCACHE/plog/blogitem-040601-1/index.html.gz -ot ../peterbecom-static-content/_FSCACHE/plog/blogitem-040601-1/index.html ]; then
        echo "OH NO! index.html is older than index.html.gz!!!"
        rm ../peterbecom-static-content/_FSCACHE/plog/blogitem-040601-1/index.html.gz
        exit 1
    else
        echo "All is well."
    fi
else
    echo "The file index.html.gz doesn't even exist"
fi


echo "Finished at..."
echo `date`
echo ""
