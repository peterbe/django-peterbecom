from peterbecom.base.basecommand import BaseCommand

from peterbecom.podcasttime.scraper import fix_podcast_images


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('--limit', default=100)

    def _handle(self, **options):
        limit = int(options['limit'])
        verbose = int(options['verbosity']) >= 2

        fix_podcast_images(limit=limit, verbose=verbose)
