from django.core.urlresolvers import reverse
from django.template import defaultfilters
from django.contrib.staticfiles.storage import staticfiles_storage
from jingo import register


@register.function
def url(viewname, *args, **kwargs):
    """Helper for Django's ``reverse`` in templates."""
    return reverse(viewname, args=args, kwargs=kwargs)


@register.function
def static(path):
    return staticfiles_storage.url(path)


@register.function
def floatformat(*args, **kwargs):
    return defaultfilters.floatformat(*args, **kwargs)
