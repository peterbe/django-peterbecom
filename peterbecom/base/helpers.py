import time
import json

import jinja2

from django.db.utils import IntegrityError

from jingo import register
from sorl.thumbnail import get_thumbnail


@register.function
def thousands(n):
    return format(n, ',')


@register.function
def thumbnail(imagefile, geometry, **options):
    if not options.get('format'):
        # then let's try to do it by the file name
        filename = imagefile
        if hasattr(imagefile, 'name'):
            # it's an ImageFile object
            filename = imagefile.name
        if filename.lower().endswith('.png'):
            options['format'] = 'PNG'
        else:
            options['format'] = 'JPEG'
    try:
        return get_thumbnail(imagefile, geometry, **options)
    except IntegrityError:
        # The write is not transactional, and since this is most likely
        # used in a write-view, we might get conflicts trying to write and a
        # remember. Just try again a little bit later.
        time.sleep(1)
        return thumbnail(imagefile, geometry, **options)


@register.function
def json_print(*args, **kwargs):
    dump = json.dumps(*args, **kwargs)
    dump = dump.replace("</", "<\\/")  # so you can't escape with a </script>
    return jinja2.Markup(dump)
