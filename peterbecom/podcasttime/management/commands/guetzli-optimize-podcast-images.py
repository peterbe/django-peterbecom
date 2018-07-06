import shutil
import os
import subprocess
import tempfile
import time

from django.conf import settings
from django.db.models import Q
from django.template.defaultfilters import filesizeformat

from peterbecom.base.basecommand import BaseCommand
from peterbecom.podcasttime.models import Podcast


class YUVColorError(Exception):
    """When you get the
    'Only YUV color space input jpeg is supported\nGuetzli processing failed'
    error."""


def check_output(cmd):
    pipes = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    std_out, std_err = pipes.communicate()
    if pipes.returncode == 1:
        err_msg = "%s. Code: %s" % (std_err.strip(), pipes.returncode)
        raise YUVColorError(err_msg)
    if pipes.returncode != 0:
        # an error happened!
        err_msg = "%s. Code: %s" % (std_err.strip(), pipes.returncode)
        raise Exception(err_msg)
    return std_out.strip()


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--limit", default=10)

    def _handle(self, **options):
        limit = int(options["limit"])
        qs = Podcast.objects.filter(
            Q(image__iendswith=".jpg") | Q(image__iendswith=".png")
        )
        savings = []
        times = []
        skips = 0
        with tempfile.TemporaryDirectory() as tmp_dir:
            for podcast in qs.order_by("?")[:limit]:
                try:
                    path = podcast.image.path
                except ValueError:
                    continue
                if not os.path.isfile(path):
                    print("Not a file", path)
                    continue
                log_file = path + ".guetzlied"
                if os.path.isfile(log_file):
                    skips += 1
                    continue
                ext = os.path.splitext(path)[1]
                if not ext:
                    continue
                # if ext not in ('.jpg', '.jpeg'):
                if ext not in (".jpg", ".jpeg", ".png"):
                    # print('Unrecognized extension {!r}'.format(ext))
                    continue

                if not os.path.isfile(path):
                    print("Completely missing image path", path)
                    podcast.image = None
                    podcast.save()
                    continue
                if not os.stat(path).st_size:
                    print("Completely empty image", path)
                    os.remove(path)
                    podcast.image = None
                    podcast.save()
                    continue

                tmp_path = os.path.join(tmp_dir, os.path.basename(path))
                cmd = [settings.GUETZLI_PATH, "--quality", "90", path, tmp_path]
                t0 = time.time()
                try:
                    out = check_output(cmd)
                except YUVColorError as exception:
                    self.notice(exception)
                    with open(log_file, "w") as f:
                        f.write(
                            "{} ({})".format(exception.__class__.__name__, exception)
                        )
                    continue
                if out:
                    self.warning(out)
                t1 = time.time()

                size_before = os.stat(path).st_size
                size_after = os.stat(tmp_path).st_size
                if size_after < size_before:
                    shutil.move(tmp_path, path)
                with open(log_file, "w") as f:
                    msg = "From {} to {} ({})\n".format(
                        filesizeformat(size_before),
                        filesizeformat(size_after),
                        filesizeformat(size_after - size_before),
                    )
                    self.out(path)
                    self.out(msg)
                    f.write(msg)
                if size_after < size_before:
                    savings.append(size_before - size_after)
                times.append(t1 - t0)
        if savings:
            self.out("SUM savings:", filesizeformat(sum(savings)))
            avg = sum(savings) / len(savings)
            self.out("AVG savings:", filesizeformat(avg))
            self.out("SUM times:", sum(times))
            avg_time = sum(times) / len(times)
            self.out("AVG times:", avg_time)

        self.out("{} skips".format(skips))
