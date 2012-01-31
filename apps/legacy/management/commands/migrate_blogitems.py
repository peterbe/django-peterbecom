from pprint import pprint
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.legacy.models import LegacyBlogitem
from apps.plog.models import BlogItem, Category

class Command(BaseCommand):

    #@transaction.commit_manually
    def handle(self, **options):
        print "MIGRATING", LegacyBlogitem.objects.all().count(), "BLOG ITEMS"
        BlogItem.objects.all().delete()
        map = {}
        categories = {}

        for b in LegacyBlogitem.objects.all():
            n = BlogItem.objects.create(
              oid=b.oid,
              title=b.title,
              alias=b.alias,
              bookmark=bool(b.bookmark),
              text=b.text,
              summary=b.summary,
              url=b.url,
              pub_date=b.pub_date,
              display_format=b.display_format,
              plogrank=b.plogrank,
              keywords=[x.strip() for x in b.keywords.split('|') if x.strip()],
              codesyntax=b.codesyntax_display_format,
            )
            #map[b.oid] = n.pk
            for cat in [x.strip() for x in b.itemcategories.split('|') if x.strip()]:
                if cat not in categories:
                    categories[cat] = Category.objects.create(name=cat)
                n.categories.add(categories[cat])
            n.save()
