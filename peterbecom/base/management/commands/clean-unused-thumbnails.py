import time
from pathlib import Path

from django.core.management.base import BaseCommand
from django.template.defaultfilters import filesizeformat

from peterbecom.plog.models import BlogItem


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--limit", default=100)
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Print instead of deleting",
        )

    def handle(self, **options):
        limit = int(options["limit"])
        dry_run = options["dry_run"]
        deleted_size = []

        def walk(directory):
            if len(deleted_size) >= limit:
                return
            for file in directory.iterdir():
                if file.is_dir():
                    walk(file)
                else:
                    for blogitem in BlogItem.objects.filter(
                        text__contains=file.name
                    ).values("title"):
                        print(blogitem)
                        break
                    else:
                        age = time.time() - file.stat().st_mtime
                        age_days = age / 60 / 60 / 24
                        age_years = age_days / 365
                        if age_years < 1:
                            continue
                        size = file.stat().st_size
                        print(
                            file,
                            "is not used in any blog post",
                            filesizeformat(size),
                            formatseconds(age),
                        )
                        if not dry_run:
                            file.unlink()
                        deleted_size.append(size)
                        if len(deleted_size) == limit:
                            return

        walk(Path("cache"))

        print(
            "Deleted, in total",
            len(deleted_size),
            "files, totalling",
            filesizeformat(sum(deleted_size)),
        )


def formatseconds(seconds):
    minutes = seconds / 60
    hours = minutes / 60
    days = hours / 24
    years = days / 365
    if years > 1:
        return "{} years".format(int(years))
    if days > 1:
        return "{} days".format(int(days))
    return "{} hours".format(int(hours))
