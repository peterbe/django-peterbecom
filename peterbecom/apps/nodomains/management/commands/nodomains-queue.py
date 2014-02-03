import datetime

from django.core.management.base import BaseCommand
from django.core.cache import cache

from peterbecom.apps.nodomains import models
from peterbecom.apps.nodomains.views import run_url
from peterbecom.apps.plog.utils import utc_now


class Command(BaseCommand):

    def handle(self, *args, **options):
        if cache.get('nodomains-queued'):
            return
        for queued in models.Queued.objects.all().order_by('add_date'):
            cache.set('nodomains-queued', True, 100)
            try:
                then = utc_now() - datetime.timedelta(days=1)
                models.Result.objects.get(
                    url=queued.url,
                    add_date__gt=then
                )
                print "Skipping", queued.url
            except models.Result.DoesNotExist:
                print queued.url
                run_url(queued.url)
            queued.delete()
        cache.delete('nodomains-queued')
