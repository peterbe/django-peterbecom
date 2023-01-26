from django.core.management.base import BaseCommand

# from peterbecom.base.basecommand import BaseCommand
from peterbecom.plog.models import BlogItem, BlogComment

# from peterbecom.plog.search import BlogItemDoc, BlogCommentDoc


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--create-index",
            action="store_true",
            default=False,
            help="create index even with limit",
        )

    def handle(self, *args, **kwargs):
        # if kwargs["create_index"]:
        #     # See this issue about the use of a private attribute
        #     # https://github.com/elastic/elasticsearch-dsl-py/issues/1164

        #     blog_item_index = BlogItemDoc._index
        #     blog_item_index.delete(ignore=404)
        #     blog_item_index.create()
        #     blog_comment_index = BlogCommentDoc._index
        #     blog_comment_index.delete(ignore=404)
        #     blog_comment_index.create()

        count, took = BlogItem.index_all_blogitems_meilisearch(verbose=True, wait=True)
        self.stdout.write(f"DONE Indexing {count:,} blog items in {took:.1f} seconds")
        count, took = BlogComment.index_all_blogcomments_meilisearch(
            verbose=True, wait=True
        )
        self.stdout.write(
            f"DONE Indexing {count:,} blog comments in {took:.1f} seconds"
        )
