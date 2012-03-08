import jinja2
from jingo import register
from django.template.loader import render_to_string
from .models import BlogItem, BlogComment, Category
from .timesince import smartertimesince
from .utils import utc_now
from django.template import Context
from django.template.loader import get_template
#from bootstrapform import

@register.function
def show_comments(parent, user):
    if parent.__class__ == BlogItem:
        filter_ = {'blogitem': parent, 'parent': None}
    else:
        filter_ = {'parent': parent}
    if not user.is_staff:
        filter_['approved'] = True
    html = []
    for comment in (BlogComment.objects
                    .filter(**filter_)
                    .order_by('add_date')):
        html.append(render_to_string('plog/comment.html', {
          'comment': comment,
          'preview': False,
          'user': user,
        }))
    return '\n'.join(html)


@register.function
def line_indent(text):
    print "WORK HARDER ON THIS"
    print repr(text)
    return text

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
