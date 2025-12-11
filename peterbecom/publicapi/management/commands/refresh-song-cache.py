from django.core.management.base import BaseCommand

from peterbecom.publicapi.views.lyrics_utils import refresh_song_cache


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--max-refresh-count", default=10)
        parser.add_argument("--random-sample-size", default=1_000)
        parser.add_argument("--sleep-time", default=1)
        parser.add_argument("--min-percent-left", default=20)

    def handle(self, **options):
        max_refresh_count = int(options["max_refresh_count"])
        random_sample_size = int(options["random_sample_size"])
        sleep_time = int(options["sleep_time"])
        min_percent_left = float(options["min_percent_left"])
        refresh_song_cache(
            max_refresh_count=max_refresh_count,
            random_sample_size=random_sample_size,
            sleep_time=sleep_time,
            min_percent_left=min_percent_left,
        )
