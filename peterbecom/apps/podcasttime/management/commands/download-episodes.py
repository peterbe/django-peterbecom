from django.core.management.base import BaseCommand

from peterbecom.apps.podcasttime.scraper import download_some_episodes


class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        max_ = 4
        verbose = int(kwargs['verbosity']) >= 2
        download_some_episodes(max_=max_, verbose=verbose)
