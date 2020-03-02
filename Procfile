elasticsearch: cd /Users/peterbe/dev/PETERBECOM/elasticsearch-6.2.1 && ./bin/elasticsearch -q
web: ./bin/run.sh web
#web: DJANGO_SETTINGS_MODULE=peterbecom.settings uwsgi -H ~/virtualenvs/django-peterbecom/ --http-socket :8000 --wsgi-file django_wsgi.py --enable-threads --master --processes 2 --threads 6
minimalcss: cd minimalcss && PORT=5000 yarn run start
#huey: ./manage.py run_huey --flush-locks --huey-verbose
huey: ./manage.py run_huey --flush-locks
adminui: cd adminui && REACT_APP_WS_URL=ws://localhost:8080 REACT_APP_BASE_URL=http://peterbecom.local BROWSER=none PORT=4000 yarn start
pulse: cd pulse && yarn run dev
