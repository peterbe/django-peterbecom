import os
import tempfile

from PIL import Image

from django.conf import settings
from django.db.models import Q
from django.template.defaultfilters import filesizeformat

from peterbecom.base.basecommand import BaseCommand
from peterbecom.podcasttime.models import Podcast


# class ImageError(Exception):
#     """re-wrap when there's something wrong about the image"""


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--limit", default=1000)

    def _handle(self, **options):
        limit = int(options["limit"])
        qs = Podcast.objects.filter(
            Q(image__iendswith=".jpg") | Q(image__iendswith=".png")
        )
        self.out("Podcasts possible: {}".format(qs.count()))
        iterator = qs.order_by("?")[:limit]
        with tempfile.TemporaryDirectory() as tmp_directory:
            self._process(tmp_directory, iterator)
        self.out("Podcasts left: {}".format(qs.count()))

    @staticmethod
    def _basename(fullpath):
        return fullpath.replace(settings.MEDIA_ROOT, "")

    def _process(self, tmp_directory, iterator):
        savings = []
        skips = 0
        for podcast in iterator:
            try:
                path = podcast.image.path
            except ValueError:
                self.warning(
                    "{!r} doesn't have an image ({!r})".format(podcast, podcast.image)
                )
                # Instead of a <ImageFieldFile: None> instance, whatever
                # nonsense that is.
                podcast.image = None
                podcast.save()
                continue
            if not os.path.isfile(path):
                self.warning("Not a file", self._basename(path))
                continue
            log_file = path + ".optimized"
            if os.path.isfile(log_file):
                skips += 1
                with open(log_file) as f:
                    self.out(
                        "{} ({}) was already optimized [{}]".format(
                            self._basename(path),
                            filesizeformat(os.stat(path).st_size),
                            f.read().strip(),
                        )
                    )
                continue
            else:
                self.out(
                    "Opening {} ({})".format(
                        self._basename(path), filesizeformat(os.stat(path).st_size)
                    )
                )
            try:
                img = Image.open(path)
            except OSError:
                self.warning("Completely broken image {}".format(self._basename(path)))
                os.remove(path)
                podcast.image = None
                podcast.save()
                continue
            w, h = img.size
            if w * h > 1300 * 1300:
                ext = os.path.splitext(path)[1]
                if not ext:
                    continue
                if ext not in (".jpg", ".jpeg", ".png"):
                    self.notice("Unrecognized extension {!r}".format(ext))
                    continue

                w2 = 1300
                h2 = int(w2 * h / w)
                try:
                    img.thumbnail((w2, h2))
                except OSError as exception:
                    podcast.image = None
                    podcast.save()
                    continue
                    # raise ImageError('{!r} CAUSED {}'.format(
                    #     podcast,
                    #     exception
                    # ))
                options = {"quality": 95}

                if ext in (".jpg", ".jpeg"):
                    options["progressive"] = True
                size_before = os.stat(path).st_size
                tmp_path = os.path.join(tmp_directory, os.path.basename(path))
                self.out("Saving {}".format(tmp_path))
                try:
                    img.save(tmp_path, **options)
                except OSError as exception:
                    self.error(
                        "OSError when saving {} ({})".format(tmp_path, exception)
                    )
                    continue
                size_after = os.stat(tmp_path).st_size
                if size_after >= size_before:
                    self.notice("{} >= after save".format(self._basename(path)))
                    os.remove(tmp_path)
                else:
                    # Swap the old one for the new one
                    os.rename(tmp_path, path)

                with open(log_file, "w") as f:
                    f.write(
                        "From {}, ({} bytes) to {} ({} bytes)\n".format(
                            (w, h),
                            format(size_before, ","),
                            (w2, h2),
                            format(size_after, ","),
                        )
                    )
                if size_after < size_before:
                    savings.append(size_before - size_after)
            else:
                self.out("{} too little ({}x{})".format(self._basename(path), w, h))

        if savings:
            self.out("SUM savings:", filesizeformat(sum(savings)))
            avg = sum(savings) / len(savings)
            self.out("AVG savings:", filesizeformat(avg))

        self.out("{} skips".format(skips))
