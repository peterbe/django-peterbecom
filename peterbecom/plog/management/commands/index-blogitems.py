from django.core.management.base import BaseCommand

from peterbecom.plog.models import BlogComment, BlogItem

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
        self._index_search_terms(keep, verbose=verbose)
        self._index_blogcomments(keep, verbose=verbose)

    def _index_blogitems(self, keep, verbose=False):
        count, took, index_name = BlogItem.index_all_blogitems(verbose=verbose)
        self.stdout.write(
            self.style.SUCCESS(
                f"DONE Indexing {count:,} blog items into {index_name!r} "
                f"in {took:.1f} seconds"
            )
        )

    def _index_blogcomments(self, keep, verbose=False):
        count, took, index_name = BlogComment.index_all_blogcomments(verbose=verbose)
        self.stdout.write(
            self.style.SUCCESS(
                f"DONE Indexing {count:,} blog comments into {index_name!r} "
                f"in {took:.1f} seconds"
            )
        )

    def _index_search_terms(self, keep, verbose=False):
        count, took, index_name = BlogItem.index_all_search_terms(verbose=verbose)
        self.stdout.write(
            self.style.SUCCESS(
                f"DONE Indexing {count:,} search terms into {index_name!r} "
                f"in {took:.1f} seconds"
            )
        )
