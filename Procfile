elasticsearch: cd /Users/peterbe/dev/PETERBECOM/elasticsearch-6.2.1 && ./bin/elasticsearch
web: ./bin/run.sh web
#web: DJANGO_SETTINGS_MODULE=peterbecom.settings uwsgi -H ~/virtualenvs/django-peterbecom/ --http-socket :8000 --wsgi-file django_wsgi.py --enable-threads --master --processes 2 --threads 6
minimalcss: cd minimalcss && PORT=5000 yarn run start
#worker: ./bin/run.sh worker-purge
huey: ./manage.py run_huey --flush-locks --huey-verbose
adminui: cd adminui && REACT_APP_BASE_URL=http://peterbecom.local BROWSER=none PORT=4000 yarn start
