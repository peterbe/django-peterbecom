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

echo "Finished at..."
echo `date`
echo ""
