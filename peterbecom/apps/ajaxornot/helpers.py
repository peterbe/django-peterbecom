import json

import jinja2
from jingo import register


@register.function
def json_print(*args, **kwargs):
    dump = json.dumps(*args, **kwargs)
    dump = dump.replace("</", "<\\/")  # so you can't escape with a </script>
    return jinja2.Markup(dump)
