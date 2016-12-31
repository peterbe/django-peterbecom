from peterbecom.base.basecommand import BaseCommand
from peterbecom.podcasttime.scraper import find_podcasts
from peterbecom.podcasttime.models import Podcast


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('baseurl')

    def handle(self, *args, **kwargs):
        verbose = int(kwargs['verbosity']) >= 2
        baseurl = kwargs['baseurl']
        self.print_stats('BEFORE')
        list(find_podcasts(baseurl, verbose=verbose))
        self.print_stats('AFTER')

    def print_stats(self, prefix):
        self.notice(prefix, Podcast.objects.all().count(), 'podcasts')
