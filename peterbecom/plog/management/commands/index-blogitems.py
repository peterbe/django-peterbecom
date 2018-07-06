import time
from collections import defaultdict

from django.conf import settings

from elasticsearch_dsl.connections import connections
from elasticsearch.helpers import streaming_bulk

from peterbecom.base.basecommand import BaseCommand
from peterbecom.plog.models import BlogItem, Category, BlogComment
from peterbecom.plog.search import blog_item_index, blog_comment_index


def _get_doc_type_name(model):
    return model._meta.verbose_name.lower().replace(" ", "_")


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--create-index",
            action="store_true",
            default=False,
            help="create index even with limit",
        )

    def _handle(self, *args, **kwargs):
        if kwargs["create_index"]:
            blog_item_index.delete(ignore=404)
            blog_item_index.create()
            blog_comment_index.delete(ignore=404)
            blog_comment_index.create()

        self._index_all_blogitems()
        self._index_all_blogcomments()

    def _index_all_blogitems(self):
        iterator = BlogItem.objects.all()
        category_names = dict((x.id, x.name) for x in Category.objects.all())
        categories = defaultdict(list)
        for e in BlogItem.categories.through.objects.all():
            categories[e.blogitem_id].append(category_names[e.category_id])

        es = connections.get_connection()
        report_every = 100
        count = 0
        doc_type_name = _get_doc_type_name(BlogItem)
        t0 = time.time()
        for success, doc in streaming_bulk(
            es,
            (m.to_search(all_categories=categories).to_dict(True) for m in iterator),
            index=settings.ES_BLOG_ITEM_INDEX,
            doc_type=doc_type_name,
        ):
            if not success:
                print("NOT SUCCESS!", doc)
            count += 1
            if not count % report_every:
                print(count)
        t1 = time.time()

        self.out("DONE Indexing {} blogitems in {} seconds".format(count, t1 - t0))

    def _index_all_blogcomments(self):
        iterator = BlogComment.objects.all().select_related("blogitem")

        es = connections.get_connection()
        report_every = 100
        count = 0
        doc_type_name = _get_doc_type_name(BlogComment)
        t0 = time.time()
        for success, doc in streaming_bulk(
            es,
            (m.to_search().to_dict(True) for m in iterator),
            index=settings.ES_BLOG_COMMENT_INDEX,
            doc_type=doc_type_name,
        ):
            if not success:
                print("NOT SUCCESS!", doc)
            count += 1
            if not count % report_every:
                print(count)
        t1 = time.time()

        self.out("DONE Indexing {} blog comments in {} seconds".format(count, t1 - t0))
