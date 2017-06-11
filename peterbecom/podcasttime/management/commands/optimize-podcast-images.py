import os

from PIL import Image

from django.template.defaultfilters import filesizeformat

from peterbecom.base.basecommand import BaseCommand
from peterbecom.podcasttime.models import Podcast


class Command(BaseCommand):

    def _handle(self, *args, **kwargs):
        qs = Podcast.objects.filter(image__isnull=False)
        savings = []
        skips = 0
        for podcast in qs.order_by('?')[:1000]:
            try:
                path = podcast.image.path
            except ValueError:
                continue
            if not os.path.isfile(path):
                print("Not a file", path)
                continue
            log_file = path + '.optimized'
            if os.path.isfile(log_file):
                skips += 1
                continue
            try:
                img = Image.open(path)
            except OSError:
                print("Completely broken image", path)
                os.remove(path)
                podcast.image = None
                podcast.save()
                continue
            w, h = img.size
            if w * h > 1300 * 1300:
                ext = os.path.splitext(path)[1]
                if not ext:
                    continue
                if ext not in ('.jpg', '.jpeg', '.png'):
                    print('Unrecognized extension {!r}'.format(ext))
                    continue

                w2 = 1300
                h2 = int(w2 * h / w)
                img.thumbnail((w2, h2))
                options = {
                    'quality': 95,
                }

                if ext in ('.jpg', '.jpeg'):
                    options['progressive'] = True
                size_before = os.stat(path).st_size
                print(path)
                img.save(path, **options)
                size_after = os.stat(path).st_size
                with open(log_file, 'w') as f:
                    f.write(
                        'From {}, ({} bytes) to {} ({} bytes)\n'.format(
                            (w, h),
                            format(size_before, ','),
                            (w2, h2),
                            format(size_after, ','),
                        )
                    )
                savings.append(size_before - size_after)

        if savings:
            self.out("SUM savings:", filesizeformat(sum(savings)))
            avg = sum(savings) / len(savings)
            self.out("AVG savings:", filesizeformat(avg))

        self.out('{} skips'.format(skips))
