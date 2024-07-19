from django import forms

from peterbecom.plog.models import BlogComment, BlogItem


class SubmitForm(forms.Form):
    oid = forms.CharField()
    comment = forms.CharField(max_length=10_000)
    parent = forms.CharField(required=False)
    name = forms.CharField(required=False)
    email = forms.EmailField(required=False)
    hash = forms.CharField(required=False)

    def clean_oid(self):
        value = self.cleaned_data["oid"]
        try:
            return BlogItem.objects.get(oid__iexact=value)
        except BlogItem.DoesNotExist:
            raise forms.ValidationError("blogitem does not exist")

    def clean_parent(self):
        value = self.cleaned_data["parent"]
        if value:
            return BlogComment.objects.get(oid=value)

    def clean_comment(self):
        return self.cleaned_data["comment"].strip()


class SearchForm(forms.Form):
    q = forms.CharField(max_length=80)
    debug = forms.BooleanField(required=False)

    CHOICES = ("multiply", "sum", "avg")
    popularity_factor = forms.FloatField(required=False)
    boost_mode = forms.ChoiceField(choices=[(x, x) for x in CHOICES], required=False)

    def clean_q(self):
        value = self.cleaned_data["q"]
        return value
