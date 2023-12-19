import json

import jinja2

from django.urls import reverse

from django_jinja import library


@library.global_function
def url(viewname, *args, **kwargs):
    """Helper for Django's ``reverse`` in templates."""
    return reverse(viewname, args=args, kwargs=kwargs)


@library.global_function
def thousands(n):
    return format(n, ",")
