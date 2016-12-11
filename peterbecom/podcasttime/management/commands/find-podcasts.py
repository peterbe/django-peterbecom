from django.core.management.base import BaseCommand

from peterbecom.podcasttime.scraper import find_podcasts


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('baseurl')

    def handle(self, *args, **kwargs):
        verbose = int(kwargs['verbosity']) >= 2
        baseurl = kwargs['baseurl']
        list(find_podcasts(baseurl, verbose=verbose))
