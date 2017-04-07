import datetime

from django import forms
from django.forms.fields import ChoiceField
from django.forms.widgets import Textarea
from django.utils import timezone
from django.db.models import Count

from peterbecom.plog.models import BlogItem, BlogFile, Category


class MultilineTextarea(Textarea):
    def render(self, name, value, attrs=None):
        if value:
            if isinstance(value, list):
                value = '\n'.join(value)
            else:
                raise NotImplementedError(type(value))
        return super(MultilineTextarea, self).render(name, value, attrs=attrs)


class BlogForm(forms.ModelForm):

    proper_keywords = forms.fields.CharField(
        widget=MultilineTextarea()
    )

    class Meta:
        model = BlogItem
        fields = (
            'oid',
            'title',
            'text',
            'summary',
            'url',
            'pub_date',
            'categories',
            'proper_keywords',
            'display_format',
            'codesyntax',
            'disallow_comments',
            'hide_comments',
        )

    def __init__(self, *args, **kwargs):
        super(BlogForm, self).__init__(*args, **kwargs)
        self.fields['display_format'] = ChoiceField()
        self.fields['display_format'].choices = [
            ('structuredtext', 'structuredtext'),
            ('markdown', 'markdown'),
        ]
        self.fields['url'].required = False
        self.fields['summary'].required = False
        self.fields['proper_keywords'].required = False

        # 10 was default
        self.fields['text'].widget.attrs['rows'] = 20

        all_categories = dict(
            Category.objects.all().values_list('id', 'name')
        )
        one_year = timezone.now() - datetime.timedelta(days=365)
        qs = (
            BlogItem.categories.through.objects
            .filter(blogitem__pub_date__gte=one_year)
            .values('category_id')
            .annotate(Count('category_id'))
            .order_by('-category_id__count')
        )
        category_choices = []
        used = []
        for count in qs:
            pk = count['category_id']
            combined = '{} ({})'.format(
                all_categories[pk],
                count['category_id__count']
            )
            category_choices.append(
                (pk, combined)
            )
            used.append(pk)

        category_items = all_categories.items()
        for pk, name in sorted(category_items, key=lambda x: x[1].lower()):
            if pk in used:
                continue
            combined = '{} (0)'.format(
                all_categories[pk],
            )
            category_choices.append(
                (pk, combined)
            )
        self.fields['categories'].choices = category_choices

    def clean_proper_keywords(self):
        value = self.cleaned_data['proper_keywords']
        return [x.strip() for x in value.splitlines() if x.strip()]

    def clean_oid(self):
        value = self.cleaned_data['oid']
        filter_ = BlogItem.objects.filter(oid=value)
        if self.instance:
            filter_ = filter_.exclude(oid=self.instance.oid)
        if filter_.exists():
            raise forms.ValidationError("OID already in use")
        return value


class EditBlogForm(BlogForm):

    pass


class BlogFileUpload(forms.ModelForm):

    class Meta:
        model = BlogFile
        exclude = ('add_date', 'modify_date')


class CalendarDataForm(forms.Form):

    start = forms.DateTimeField()
    end = forms.DateTimeField()

    def clean(self):
        cleaned_data = super(CalendarDataForm, self).clean()
        if 'start' in cleaned_data and 'end' in cleaned_data:
            if cleaned_data['start'] > cleaned_data['end']:
                raise forms.ValidationError('start > end')
            diff = cleaned_data['end'] - cleaned_data['start']
            if diff > datetime.timedelta(days=50):
                raise forms.ValidationError('> 50 days')
        return cleaned_data
