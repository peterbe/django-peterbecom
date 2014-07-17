import time

from django.core.management.base import BaseCommand

from peterbecom.apps.plog import models
from peterbecom.apps.plog.utils import utc_now
from peterbecom.apps.homepage.views import STOPWORDS
from peterbecom.apps.redisutils import get_redis_connection
from peterbecom.apps.redis_search_index import RedisSearchIndex


class Command(BaseCommand):

    def handle(self, *args, **options):
        now = utc_now()

        connection = get_redis_connection('titles')
        search_index = RedisSearchIndex(connection)

        query = u' '.join(args)
        print "QUERY:", repr(query)
        t0 = time.time()
        results = search_index.search(query)
        t1 = time.time()
        print "In", t1 - t0, "seconds"
        print "TERMS:", results['terms']
        for id, score, title in results['results']:
            print "\t", id.ljust(4), score, repr(title)
