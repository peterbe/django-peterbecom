from pprint import pprint
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.legacy.models import LegacyBlogitem, LegacyBlogcomment
from apps.plog.models import BlogItem, BlogComment

class Command(BaseCommand):

    #@transaction.commit_manually
    def handle(self, **options):
        print "MIGRATING", LegacyBlogcomment.objects.all().count(), "BLOG COMMENTS"
        BlogComment.objects.all().delete()
        map = {}

        _blogitems = {}
        def get_blogitem(oid):
            if oid not in _blogitems:
                try:
                    _blogitems[oid] = BlogItem.objects.get(oid=oid)
                except BlogItem.DoesNotExist:
                    print "OID", repr(oid)
                    raise
            return _blogitems[oid]

        def get_blogcomment(oid):
            try:
                return BlogComment.objects.get(oid=oid)
            except BlogComment.DoesNotExist:
                print "WARNING BlogComment with oid=%r doesn't exist" % oid

        root_comments = {}
        for b in LegacyBlogcomment.objects.all().order_by('add_date'):
            n = BlogComment.objects.create(
              oid=b.oid,
              approved=b.approved,
              name=b.name,
              email=b.email,
              add_date=b.add_date,
              comment=b.comment,
            )
            if b.root:
                n.blogitem = get_blogitem(b.parent_oid)
                n.parent = None
                n.save()
                root_comments[n.pk] = n.blogitem
            else:
                n.parent = get_blogcomment(b.parent_oid)
                n.save()
            map[b.oid] = n

#        for b in LegacyBlogcomment.objects.filter(root=False):
#            comment = map[b.oid]
#            comment.parent = map[b.parent_oid]
#            comment.blogitem = find_parent_blogitem(comment)
#            comment.save()
