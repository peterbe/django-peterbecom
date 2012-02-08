import jinja2
from jingo import register
from django.template.loader import render_to_string
from .models import BlogItem, BlogComment, Category


@register.function
def show_comments(parent):
    if parent.__class__ == BlogItem:
        filter_ = {'blogitem': parent, 'parent': None}
    else:
        filter_ = {'parent': parent}
    html = []
    for comment in (BlogComment.objects
                    .filter(**filter_)
                    .exclude(approved=False)
                    .order_by('add_date')):
        html.append(render_to_string('plog/comment.html', {
          'comment': comment,
          'preview': False,
        }))
    return '\n'.join(html)
