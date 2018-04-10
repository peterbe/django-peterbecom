from django import forms
from django.utils import dateparse


class BlogitemsFilterForm(forms.Form):

    since = forms.CharField(required=False)

    def clean_since(self):
        value = self.cleaned_data['since']
        if value:
            return dateparse.parse_datetime(value)
        return value
