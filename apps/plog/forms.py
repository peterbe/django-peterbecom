from django import forms
from django.forms.fields import ChoiceField
from django.forms.widgets import Textarea
from apps.plog.models import BlogItem, BlogFile


class MultilineTextarea(Textarea):
    def render(self, name, value, attrs=None):
        if value:
            value = '\n'.join(value)
        return super(MultilineTextarea, self).render(name, value, attrs=attrs)

class BlogForm(forms.ModelForm):

    class Meta:
        model = BlogItem
        exclude = ('alias', 'bookmark', 'text_rendered', 'plogrank',
                   'modify_date')

    def __init__(self, *args, **kwargs):
        super(BlogForm, self).__init__(*args, **kwargs)
        self.fields['display_format'] = ChoiceField()
        self.fields['display_format'].choices = [
          ('structuredtext', 'structuredtext'),
          ('markdown', 'markdown'),
        ]
        self.fields['keywords'].widget = MultilineTextarea()
        self.fields['url'].required = False
        self.fields['summary'].required = False
        self.fields['keywords'].required = False


class EditBlogForm(BlogForm):

    pass


class BlogFileUpload(forms.ModelForm):

    class Meta:
        model = BlogFile
        exclude = ('add_date', 'modify_date')
