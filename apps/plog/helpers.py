import textwrap
import jinja2
from jingo import register
from django.template.loader import render_to_string
from .models import BlogItem, BlogComment, Category
from .timesince import smartertimesince
from .utils import utc_now
from django.conf import settings
from django.template import Context
from django.template.loader import get_template
from apps.plog.models import BlogFile
from sorl.thumbnail import get_thumbnail
#from bootstrapform import

@register.function
def show_comments(parent, is_staff, all_comments):
    if parent.__class__ == BlogItem:
        parent = None
    else:
        parent = parent.pk
    html = []
    comments = all_comments[parent]
    for comment in comments:
        html.append(render_to_string('plog/comment.html', {
          'comment': comment,
          'preview': False,
          'is_staff': is_staff,
          'all_comments': all_comments,
        }))
    return '\n'.join(html)


@register.function
def line_indent(text, indent=' ' * 4):
    return '\n'.join(textwrap.wrap(text,
                                   initial_indent=indent,
                                   subsequent_indent=indent))

@register.function
def timesince(date):
    if date.tzinfo:
        return smartertimesince(date, utc_now())
    else:
        return smartertimesince(date)


@register.function
def bootstrapform(form):
    template = get_template("bootstrapform/form.html")
    context = Context({'form': form})
    return template.render(context)


@register.function
def expand_carousel(html, post):
    if '::carousel::' in html:
        thumbnails = get_photos(post, '900x900')
        html = html.replace('::carousel::',
                            render_to_string('plog/carousel.html', thumbnails))

    return html

@register.function
def expand_carousel_thumbnails(html, post):
    if '::carousel::' in html:
        thumbnails = get_photos(post, '100x100')
        html = html.replace('::carousel::',
                         render_to_string('plog/thumbnails.html',
                                          dict(thumbnails, post=post)))
    return html



def get_photos(post, size):
    photos = []
    sizes = []
    for blogfile in BlogFile.objects.filter(blogitem=post).order_by('add_date'):
        im = get_thumbnail(blogfile.file, size, #crop='center',
                           quality=81, upscale=False)

        im.full_url = settings.STATIC_URL + im.url
        sizes.append((im.width, im.height))
        im.title = blogfile.title
        photos.append(im)
    return {
      'photos': photos,
      'min_height': min(x[1] for x in sizes),
      'min_width': min(x[0] for x in sizes),
      'max_height': max(x[1] for x in sizes),
      'max_width': max(x[0] for x in sizes),
    }


@register.function
def min_(*args):
    return min(*args)
