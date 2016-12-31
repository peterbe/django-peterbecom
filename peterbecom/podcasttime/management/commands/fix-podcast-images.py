from peterbecom.base.basecommand import BaseCommand

from peterbecom.podcasttime.scraper import fix_podcast_images


class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        max_ = 10
        verbose = int(kwargs['verbosity']) >= 2
        fix_podcast_images(max_=max_, verbose=verbose)
