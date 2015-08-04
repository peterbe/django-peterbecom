import datetime

from django.core.management.base import BaseCommand
from django.core.cache import cache

from peterbecom.apps.nodomains import models
from peterbecom.apps.nodomains.tasks import run_url
from peterbecom.apps.plog.utils import utc_now


class Command(BaseCommand):

    def handle(self, *args, **options):
        if cache.get('nodomains-queued'):
            return
        queued = models.Queued.objects.filter(failed_attempts__lt=5)
        for queued in queued.order_by('add_date'):
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
                try:
                    run_url(queued.url)
                except Exception:
                    queued.failed_attempts += 1
                    queued.save()
                    continue
            queued.delete()
        cache.delete('nodomains-queued')
