#!/bin/bash
LOGFILE=/var/log/django/insert-songsearch-autocomplete.log
exec >> $LOGFILE 2>&1

cd /home/django/django-peterbecom/songsearch-autocomplete
rm -fr ../peterbecom-static-content/songsearch-autocomplete
aunpack -X ../peterbecom-static-content/ songsearch-autocomplete.zip

./_insert.py
echo "Finished at..."
echo `date`
echo ""
