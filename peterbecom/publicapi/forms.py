import re

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
            try:
                return BlogComment.objects.get(oid=value)
            except BlogComment.DoesNotExist:
                raise forms.ValidationError("parent comment does not exist")

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
        value, config = extract_search_config(value)
        if not value:
            raise forms.ValidationError("No search terms left after extracting config")
        self.cleaned_data["_config"] = config
        return value


def extract_search_config(value):
    config = {"in_title": False, "no_fuzzy": False}
    in_title_regex = re.compile(r"\bin:\s?title\b")
    if in_title_regex.search(value):
        value = in_title_regex.sub("", value)
        config["in_title"] = True

    no_fuzzy_regex = re.compile(r"\bno:\s?fuzzy?\b")
    if no_fuzzy_regex.search(value):
        value = no_fuzzy_regex.sub("", value)
        config["no_fuzzy"] = True

    return value.strip(), config
