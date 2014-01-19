from django.core.management.base import BaseCommand
from django.core.cache import cache

from peterbecom.apps.nodomains import models
from peterbecom.apps.nodomains.views import run_url


class Command(BaseCommand):

    def handle(self, *args, **options):
        if cache.get('nodomains-queued'):
            return
        cache.set('nodomains-queued', True, 60)
        for queued in models.Queued.objects.all().order_by('add_date'):
            print queued.url
            run_url(queued.url)
            queued.delete()
        cache.delete('nodomains-queued')
