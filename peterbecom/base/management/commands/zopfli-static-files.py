import glob
import os
import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.template.defaultfilters import filesizeformat

from peterbecom.zopfli_file import zopfli_file


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Print instead of deleting",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            default=False,
            help="Ignore already existing .gz files",
        )
        parser.add_argument(
            "-i",
            type=int,
            default=500,
            help="iterations argument to zopfli (default 500)",
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=60,
            help="timeout argument to zopfli_file (default 60)",
        )
        parser.add_argument(
            "--too-old-days",
            type=int,
            default=100,
            help="Files too old. Will be ignored. (Default 100)",
        )

    def handle(self, **options):
        i = options["i"]
        timeout = options["timeout"]
        verbose = options["verbosity"] > 1
        too_old_days = options["too_old_days"]
        files = glob.glob(os.path.join(settings.STATIC_ROOT, "**", "*.js")) + glob.glob(
            os.path.join(settings.STATIC_ROOT, "**", "*.css")
        )
        now = time.time()
        count = 0
        times = []
        for file in files:
            age = now - os.stat(file).st_mtime
            age_days = age / (60 * 60 * 24)
            if age_days > too_old_days:
                if options["verbosity"] > 2:
                    print(file, "Too old!", round(age_days, 1), "days old")
                continue

            if options["force"] or not os.path.isfile(file + ".gz"):
                count += 1
                if options["dry_run"]:
                    print("zopfli_file({})".format(file))
                else:
                    if verbose:
                        print(
                            "Zopflying", file.replace(settings.STATIC_ROOT, ""), "..."
                        )
                    t0 = time.time()
                    file_gz = zopfli_file(file, i=i, timeout=timeout)
                    t1 = time.time()
                    if verbose:
                        print(
                            "\ttook",
                            "{:.1f}s".format(t1 - t0),
                            filesizeformat(os.stat(file).st_size).ljust(6),
                            "->",
                            filesizeformat(os.stat(file_gz).st_size),
                        )
                    times.append(t1 - t0)

        if verbose:
            print("Zopflied", count, "files")
