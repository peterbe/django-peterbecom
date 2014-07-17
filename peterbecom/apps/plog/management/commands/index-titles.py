import re
import tokenize
from cStringIO import StringIO

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
        connection.flushdb()
        search_index = RedisSearchIndex(connection)

        for plog in models.BlogItem.objects.filter(pub_date__lte=now).order_by('?'):
            # if 'Gro' in plog.title:
            print plog.title,
            # print search_index.add_item(plog.id, plog.title, 1)
            try:
                hits = models.BlogItemHits.objects.get(oid=plog.oid).hits
            except models.BlogItemHits.DoesNotExist:
                hits = 1
            # if 'Gro' in plog.title:
            print search_index.add_item(plog.oid, plog.title, hits), hits
