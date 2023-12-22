from django.core.management.base import BaseCommand
from peterbecom.plog.models import BlogItem, BlogComment
from peterbecom.plog.search import BlogItemDoc, BlogCommentDoc, SearchTermDoc


"""
TODO (Some day)

Stop using indexes that are named after the model. Instead, use names that are
timestamped and use aliases in the search code.
"""


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--keep-index",
            action="store_true",
            default=False,
            help="Don't delete the index before indexing",
        )

    def handle(self, *args, **kwargs):
        verbose = kwargs["verbosity"] > 1

        keep = kwargs["keep_index"]
        self._index_blogitems(keep, verbose=verbose)
        self._index_blogcomments(keep, verbose=verbose)
        self._index_search_terms(keep, verbose=verbose)

    def _index_blogitems(self, keep, verbose=False):
        if not keep:
            self._delete_and_create(BlogItemDoc._index)

        count, took = BlogItem.index_all_blogitems(verbose=verbose)
        self.stdout.write(
            self.style.SUCCESS(
                f"DONE Indexing {count:,} blog items in {took:.1f} seconds"
            )
        )

    def _index_blogcomments(self, keep, verbose=False):
        if not keep:
            self._delete_and_create(BlogCommentDoc._index)

        count, took = BlogComment.index_all_blogcomments(verbose=verbose)
        self.stdout.write(
            self.style.SUCCESS(
                f"DONE Indexing {count:,} blog comments in {took:.1f} seconds"
            )
        )

    def _index_search_terms(self, keep, verbose=False):
        if not keep:
            self._delete_and_create(SearchTermDoc._index)
        count, took = BlogItem.index_all_search_terms(verbose=verbose)
        self.stdout.write(
            self.style.SUCCESS(
                f"DONE Indexing {count:,} search terms in {took:.1f} seconds"
            )
        )

    def _delete_and_create(self, index):
        index.delete(ignore=404)
        index.create()
        self.stdout.write(
            self.style.SUCCESS(f"Deleted and created index {index._name}")
        )
