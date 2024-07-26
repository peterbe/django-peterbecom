import datetime
import os

from django.conf import settings

from peterbecom.base.basecommand import BaseCommand
from peterbecom.base.xcache_analyzer import get_x_cache


class Command(BaseCommand):
    def _handle(self, **options):
        URL = "https://www.peterbe.com/plog/blogitem-040601-1"
        urls = []
        for page in range(1, settings.MAX_BLOGCOMMENT_PAGES + 1):
            if page == 1:
                url = URL
            else:
                url = URL + "/p{}".format(page)
            urls.append(url)

        state_fn = os.path.join(
            os.path.dirname(__file__), os.path.basename(__file__).split(".")[0] + ".log"
        )
        try:
            with open(state_fn) as f:
                (last_url,) = [
                    x.strip()
                    for x in f.read().strip().splitlines()
                    if x.strip() and not x.startswith("#")
                ]
        except FileNotFoundError:
            last_url = None

        if last_url and last_url in urls:
            url = urls[(urls.index(last_url) + 1) % len(urls)]
        else:
            url = urls[0]

        print("RUN", url)

        with open(state_fn, "w") as f:
            f.write("# {}\n".format(datetime.datetime.utcnow()))
            f.write(url)
            f.write("\n")

        x_cache_result = get_x_cache(url)
        from pprint import pprint

        pprint(x_cache_result)
