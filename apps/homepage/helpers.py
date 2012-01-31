from django.core.urlresolvers import reverse
from django.contrib.staticfiles.storage import staticfiles_storage


import jinja2

from jingo import register


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
