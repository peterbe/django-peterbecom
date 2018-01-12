from optparse import make_option

from django.core.management.base import BaseCommand

from peterbecom.plog.models import BlogItem


class Command(BaseCommand):

    option_list = BaseCommand.option_list + (
        make_option(
            '--base-url',
            dest='base_url',
            default='https://www.peterbe.com',
            help='Base URL for the calling URL'
        ),
    )

    def handle(self, *args, **options):
        for oid in args:
            blogitem = BlogItem.objects.get(oid=oid)
            print(blogitem.update_screenshot_image(options['base_url']))
            print(blogitem.screenshot_image)
            print()
