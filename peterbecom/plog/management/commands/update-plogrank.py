import re
import tokenize
from cStringIO import StringIO

from django.core.management.base import BaseCommand

from peterbecom.plog.models import BlogItem, BlogComment, BlogItemHits
from peterbecom.plog.utils import utc_now


class Command(BaseCommand):

    def handle(self, *args, **options):
        now = utc_now()
        verbose = int(options['verbosity']) > 1

        qs = BlogItemHits.objects.filter(hits__gt=0)
        for hit in qs.values('oid', 'hits'):
            # This is totally arbitrary!
            # I'm using hits and number of comments as a measure of
            # how is should be ranked.
            # The thinking is that posts that are found and read are
            # likely to be more popular and should thus be ranked
            # higher.
            plogrank = hit['hits']
            comments = (
                BlogComment.objects
                .filter(blogitem__oid=hit['oid']).count()
            )
            # multiple by a factor to make this slightly more significant
            plogrank += comments * 10
            (
                BlogItem.objects
                .filter(oid=hit['oid'])
                .update(plogrank=plogrank)
            )
            if verbose:
                print str(plogrank).rjust(7), '\t', hit['oid']
