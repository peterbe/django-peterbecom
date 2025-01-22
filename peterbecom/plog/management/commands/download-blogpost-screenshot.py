from django.core.management.base import BaseCommand

from peterbecom.plog.models import BlogItem


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("oid", nargs="+")
        parser.add_argument(
            "--base-url",
            dest="base_url",
            default="https://www.peterbe.com",
            help=("Base URL for the calling URL (default https://www.peterbe.com)"),
        )

    def handle(self, *args, **options):
        for oid in options["oid"]:
            blogitem = BlogItem.objects.get(oid=oid)
            print(blogitem.update_screenshot_image(options["base_url"]))
            print(blogitem.screenshot_image)
            print()
