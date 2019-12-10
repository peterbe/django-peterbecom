import datetime

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
        limit = int(options["limit"])
        verbose = int(options["verbosity"]) >= 2
        dry_run = options["dry_run"]
        comments = BlogComment.objects.filter(
            approved=False,
            add_date__gt=timezone.now() - datetime.timedelta(days=7),
            add_date__lt=timezone.now() - datetime.timedelta(hours=1),
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
