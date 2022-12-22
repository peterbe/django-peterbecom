import textwrap

from django.conf import settings
from django.template.loader import render_to_string
from django.utils.timesince import timesince as django_timesince
from django_jinja import library
from sorl.thumbnail import get_thumbnail

from peterbecom.plog.models import BlogFile, BlogItem


@library.global_function
def show_comments(parent, all_comments, depth=None):
    if parent.__class__ == BlogItem:
        parent = None
    else:
        parent = parent.pk
    html = []
    comments = all_comments[parent]
    for comment in comments:
        html.append(
            render_to_string(
                "plog/comment.html",
                {
                    "comment": comment,
                    "all_comments": all_comments,
                    "count_children": len(all_comments[comment.pk]),
                    "depth": depth or 0,
                },
            )
        )
    return "\n".join(html)


@library.global_function
def line_indent(text, indent=" " * 4):
    return "\n".join(
        textwrap.wrap(text, initial_indent=indent, subsequent_indent=indent)
    )


@library.global_function
def timesince(date, *args, **kwargs):
    return django_timesince(date, *args, **kwargs)


def get_photos(post, size):
    photos = []
    sizes = []
    files = BlogFile.objects.filter(blogitem=post).order_by("add_date")
    for blogfile in files:
        im = get_thumbnail(blogfile.file, size, quality=81, upscale=False)
        im.full_url = settings.STATIC_URL + im.url
        sizes.append((im.width, im.height))
        im.title = blogfile.title
        photos.append(im)
    return {
        "photos": photos,
        "min_height": min(x[1] for x in sizes),
        "min_width": min(x[0] for x in sizes),
        "max_height": max(x[1] for x in sizes),
        "max_width": max(x[0] for x in sizes),
    }


@library.global_function
def min_(*args):
    return min(*args)


@library.global_function
def get_category_overlap(blogitem_base, blogitem):
    intersection = blogitem.categories.filter(id__in=blogitem_base.categories.all())
    return intersection.order_by("name")
