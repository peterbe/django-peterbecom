import datetime

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from peterbecom.base.basecommand import BaseCommand
from peterbecom.plog.models import BlogComment
from peterbecom.plog.utils import rate_blog_comment
from peterbecom.api.views import actually_approve_comment


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--limit", default=25)
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Don't actually approve the good candidates",
        )

    def _handle(self, **options):
        if settings.DB_MAINTENANCE_MODE:
            print("DB maintenance mode")
            return
        limit = int(options["limit"])
        verbose = int(options["verbosity"]) >= 2
        dry_run = options["dry_run"]
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
                    self.out("Actually approved comment: {!r}".format(comment))
                else:
                    self.out("*Would* approved comment: {!r}".format(comment))
                print("\n")
                count_approved += 1
                if count_approved >= limit:
                    break

        if count_approved:
            self.out("Approved {} good comments".format(count_approved))

        # This exists so it can be displayed in the admin UI.
        cache_key = "auto-approve-good-comments"
        records = cache.get(cache_key, [])
        records.insert(0, [timezone.now(), count_approved])
        cache.set(cache_key, records[:10], 60 * 60 * 24)
