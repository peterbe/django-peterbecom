import datetime

from django.utils import timezone

from peterbecom.base.basecommand import BaseCommand
from peterbecom.plog.models import BlogComment
from peterbecom.plog.utils import rate_blog_comment
from peterbecom.api.views import actually_approve_comment


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Don't actually approve the good candidates",
        )

    def _handle(self, **options):
        dry_run = options["dry_run"]
        comments = BlogComment.objects.filter(
            approved=False, add_date__gt=timezone.now() - datetime.timedelta(days=7)
        )

        from pprint import pprint

        for comment in comments.order_by("add_date"):
            clues = rate_blog_comment(comment)

            print("Name:", repr(comment.name), "Email:", repr(comment.email))
            print("-" * 80)
            print(comment.comment)
            print(len(comment.comment))
            print("CLUES:")
            pprint(clues)
            print("\n")
            print()
            if clues["good"] and not clues["bad"]:
                if not dry_run:
                    actually_approve_comment(comment)
                    self.out("Actually approved comment: {!r}".format(comment))
                else:
                    self.out("*Would* approved comment: {!r}".format(comment))
                print("\n")
