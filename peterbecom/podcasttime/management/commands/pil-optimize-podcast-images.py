import shutil
import os
import tempfile
import time

from PIL import Image

from django.db.models import Q
from django.template.defaultfilters import filesizeformat

from peterbecom.base.basecommand import BaseCommand
from peterbecom.podcasttime.models import Podcast


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('--limit', default=100)

    def _handle(self, **options):
        limit = int(options['limit'])
        qs = Podcast.objects.filter(
            Q(image__iendswith='.jpg') | Q(image__iendswith='.png')
        )
        savings = []
        times = []
        skips = 0
        tmp_dir = tempfile.gettempdir()
        for podcast in qs.order_by('?')[:limit]:
            try:
                path = podcast.image.path
            except ValueError:
                continue
            if not os.path.isfile(path):
                print("Not a file", path)
                continue
            log_file = path + '.pillow'
            if os.path.isfile(log_file):
                skips += 1
                continue
            ext = os.path.splitext(path)[1]
            if not ext:
                continue
            if ext not in ('.jpg', '.jpeg', '.png'):
                self.warning('Unrecognized extension {!r}'.format(ext))
                continue

            if not os.path.isfile(path):
                self.warning("Completely missing image path", path)
                podcast.image = None
                podcast.save()
                continue
            if not os.stat(path).st_size:
                self.warning("Completely empty image", path)
                os.remove(path)
                podcast.image = None
                podcast.save()
                continue

            was_png = path.lower().endswith('.png')
            split = os.path.splitext(os.path.basename(path))
            if was_png:
                tmp_path = os.path.join(tmp_dir, split[0] + '.jpg')
            else:
                tmp_path = os.path.join(tmp_dir, split[0] + '.png')

            print('From {} to {}'.format(
                os.path.basename(path),
                os.path.basename(tmp_path),
            ))
            t0 = time.time()
            img = Image.open(path)
            if was_png:
                img = img.convert('RGB')
                img.save(tmp_path, 'JPEG', quality=90, optimize=True)
            else:
                try:
                    img.save(tmp_path, quality=90, optimize=True)
                except OSError as exception:
                    if 'cannot write mode CMYK as PNG' in str(exception):
                        self.notice('OSError on PNG conversion {}'.format(
                            path,
                        ))
                        continue
                    raise
            t1 = time.time()

            size_before = os.stat(path).st_size
            size_after = os.stat(tmp_path).st_size
            if size_after < size_before:
                shutil.move(tmp_path, path)
            with open(log_file, 'w') as f:
                msg = (
                    'From {} to {} ({})\n'.format(
                        filesizeformat(size_before),
                        filesizeformat(size_after),
                        filesizeformat(size_after - size_before),
                    )
                )
                self.out('{} {}'.format(
                    path,
                    msg,
                ))
                f.write(msg)
            if size_after < size_before:
                savings.append(size_before - size_after)
            times.append(t1 - t0)
        if savings:
            self.out("SUM savings:", filesizeformat(sum(savings)))
            avg = sum(savings) / len(savings)
            self.out("AVG savings:", filesizeformat(avg))
            self.out('SUM times:', sum(times))
            avg_time = sum(times) / len(times)
            self.out('AVG times:', avg_time)

        self.out('{} skips'.format(skips))
