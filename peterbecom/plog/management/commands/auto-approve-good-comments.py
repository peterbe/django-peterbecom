import datetime

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from peterbecom.api.views import actually_approve_comment
from django.core.management.base import BaseCommand
from peterbecom.plog.models import BlogComment
from peterbecom.plog.utils import rate_blog_comment


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--limit", default=25)
        parser.add_argument("--min-to-execute", default=3)
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Don't actually approve the good candidates",
        )

    def handle(self, **options):
        if settings.DB_MAINTENANCE_MODE:
            print("DB maintenance mode")
            return
        limit = int(options["limit"])
        verbose = int(options["verbosity"]) >= 2
        dry_run = options["dry_run"]
        min_to_execute = int(options["min_to_execute"])

        count_would_approve = self._run(limit, verbose, True)
        if not count_would_approve:
            print("There are no comments to auto-approve.")
        elif count_would_approve < min_to_execute:
            print(
                "There are only {} comments to auto-approve,"
                "which is less than minimum of {}".format(
                    count_would_approve, min_to_execute
                )
            )

        if not dry_run and count_would_approve >= min_to_execute:
            self._run(limit, verbose, False)

    def _run(self, limit, verbose, dry_run):
        comments = BlogComment.objects.filter(
            approved=False,
            add_date__gt=timezone.now() - datetime.timedelta(days=14),
            add_date__lt=timezone.now() - datetime.timedelta(hours=1),
            blogitem__oid="blogitem-040601-1",
        )

        def print_comment(comment):
            line = " NAME: {!r}  EMAIL: {!r} ".format(comment.name, comment.email)
            print(line.center(100, "-"))
            print(comment.comment)
            line = " LENGTH: {}  CLUES: {} ".format(len(comment.comment), clues)
            print(line.center(100, "-"))
            print()

        count_approved = 0
        for comment in comments.order_by("add_date"):
            clues = rate_blog_comment(comment)
            if verbose:
                print_comment(comment)
            if clues["good"] and not clues["bad"]:
                if comment.parent and not comment.parent.approved:
                    print("Parent not approved!")
                    continue
                if not verbose:
                    print_comment(comment)

                if not dry_run:
                    actually_approve_comment(comment, auto_approved=True)
                    self.stdout.write("Actually approved comment: {!r}".format(comment))
                else:
                    self.stdout.write("*Would* approved comment: {!r}".format(comment))
                print("\n")
                count_approved += 1
                if count_approved >= limit:
                    break

        if count_approved:
            self.stdout.write(
                "{} {} good comments".format(
                    "Would approve" if dry_run else "Approved", count_approved
                )
            )

        if dry_run:
            return count_approved

        # This exists so it can be displayed in the admin UI.
        cache_key = "auto-approve-good-comments"
        records = cache.get(cache_key, [])
        records.insert(0, [timezone.now(), count_approved])
        cache.set(cache_key, records[:10], 60 * 60 * 24)
