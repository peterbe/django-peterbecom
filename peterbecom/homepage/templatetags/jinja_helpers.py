import re

from django.urls import reverse
from django.template import defaultfilters
from django.contrib.staticfiles.storage import staticfiles_storage
from django_jinja import library

image_tags_regex = re.compile('(<img src="([^"]+)"[^>]+>)')
width_or_height_regex = re.compile('(width|height)="\d+"')


@library.global_function
def url(viewname, *args, **kwargs):
    """Helper for Django's ``reverse`` in templates."""
    return reverse(viewname, args=args, kwargs=kwargs)


@library.global_function
def static(path):
    return staticfiles_storage.url(path)


@library.global_function
def floatformat(*args, **kwargs):
    return defaultfilters.floatformat(*args, **kwargs)


@library.global_function
def make_images_lazy(html, placeholder_image_url):
    def replacer(match):
        html_tag, old_url = match.groups()
        # Only do this trick for images that have a width and height set.
        # Otherwise, when we replace our tiny placeholder image, it'll
        # appear as tiny as the placeholder PNG is. But when eventually
        # replaced, it'll appear as big as the original image.
        # That replacement might cause the page height to change
        # unnecessarily.
        if width_or_height_regex.findall(html_tag):
            new_snippet = '{}" data-originalsrc="{}'.format(
                placeholder_image_url, old_url
            )
            html_tag = html_tag.replace(old_url, new_snippet)
        else:
            html_tag = match.group()
        return html_tag

    return image_tags_regex.sub(replacer, html)
