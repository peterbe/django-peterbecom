#import re
from django.core.urlresolvers import reverse
from django.contrib.staticfiles.storage import staticfiles_storage
import jinja2
from jingo import register


#split_regex = re.compile('<!--\s*split\s*-->')


@register.function
def thisyear():
    """The current year."""
    return jinja2.Markup(datetime.date.today().year)

@register.function
def url(viewname, *args, **kwargs):
    """Helper for Django's ``reverse`` in templates."""
    return reverse(viewname, args=args, kwargs=kwargs)


@register.function
def static(path):
    return staticfiles_storage.url(path)


#@register.function
#def split_first_part(html):
#    return split_regex.split(html)[0]
