import os

from PIL import Image

from django.template.defaultfilters import filesizeformat

from peterbecom.base.basecommand import BaseCommand
from peterbecom.podcasttime.models import Podcast


class Command(BaseCommand):

    def _handle(self, *args, **kwargs):
        qs = Podcast.objects.filter(image__isnull=False)
        savings = []
        for podcast in qs.order_by('?')[:1000]:
            try:
                path = podcast.image.path
            except ValueError:
                continue
            if not os.path.isfile(path):
                print("Not a file", path)
                continue
            log_file = path + '.optimized'
            if not os.path.isfile(log_file):
                try:
                    img = Image.open(path)
                except OSError:
                    print("Completely broken image", path)
                    os.remove(path)
                    podcast.image = None
                    podcast.save()
                    continue
                w, h = img.size
                if w * h > 1400 * 1400:
                    # print(path)
                    w2 = 1400
                    h2 = int(w2 * h / w)
                    # print(img.size, (w2, h2))
                    img.thumbnail((w2, h2))
                    options = {
                        'quality': 95,
                    }
                    # print()
                    ext = os.path.splitext(path)[1]
                    if ext == '.jpg':
                        options['progressive'] = True
                    # img.save(path + '.optimized' + ext, **options)
                    size_before = os.stat(path).st_size
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
                    print(path)
                    savings.append(size_before - size_after)
                    # print(path + '.optimized' + ext)
                    # break
            # break
        if savings:
            print("SUM savings:", filesizeformat(sum(savings)))
            avg = sum(savings) / len(savings)
            print("AVG savings:", filesizeformat(avg))
