from django.core.management.base import BaseCommand

from peterbecom.apps.podcasttime.scraper import find_podcasts


class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        verbose = int(kwargs['verbosity']) >= 2
        baseurl = args[0]
        find_podcasts(baseurl, verbose=verbose)
