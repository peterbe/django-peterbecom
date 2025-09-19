import datetime
import re

from django import forms
from django.core.validators import EmailValidator
from django.db.models import Count
from django.forms.fields import ChoiceField, DateTimeField
from django.forms.widgets import Textarea
from django.utils import timezone
from django.utils.datastructures import MultiValueDict
from django.utils.dateparse import parse_datetime

from peterbecom.plog.models import (
    BlogComment,
    BlogCommentClassification,
    BlogFile,
    BlogItem,
    Category,
    SpamCommentPattern,
)


class MultilineTextarea(Textarea):
    def render(self, name, value, attrs=None, renderer=None):
        if value:
            if isinstance(value, list):
                value = "\n".join(value)
            else:
                raise NotImplementedError(type(value))
        return super(MultilineTextarea, self).render(
            name, value, attrs=attrs, renderer=renderer
        )


class ISODateTimeField(DateTimeField):
    def strptime(self, value, format):
        try:
            return parse_datetime(value)
        except Exception:
            return super().strptime(value, format)


class BlogForm(forms.ModelForm):
    pub_date = ISODateTimeField()
    proper_keywords = forms.CharField()

    class Meta:
        model = BlogItem
        fields = (
            "oid",
            "title",
            "text",
            "summary",
            "url",
            "pub_date",
            "categories",
            "proper_keywords",
            "display_format",
            "codesyntax",
            "disallow_comments",
            "hide_comments",
        )

    def __init__(self, *args, **kwargs):
        super(BlogForm, self).__init__(*args, **kwargs)
        self.fields["display_format"] = ChoiceField()
        self.fields["display_format"].choices = [
            ("structuredtext", "structuredtext"),
            ("markdown", "markdown"),
        ]
        self.fields["url"].required = False
        self.fields["summary"].required = False
        self.fields["proper_keywords"].required = False

        # 10 was default
        self.fields["text"].widget.attrs["rows"] = 20

        all_categories = dict(Category.objects.all().values_list("id", "name"))
        one_year = timezone.now() - datetime.timedelta(days=365)
        qs = (
            BlogItem.categories.through.objects.filter(blogitem__pub_date__gte=one_year)
            .values("category_id")
            .annotate(Count("category_id"))
            .order_by("-category_id__count")
        )
        category_choices = []
        used = []
        for count in qs:
            pk = count["category_id"]
            combined = "{} ({})".format(all_categories[pk], count["category_id__count"])
            category_choices.append((pk, combined))
            used.append(pk)

        category_items = all_categories.items()
        for pk, name in sorted(category_items, key=lambda x: x[1].lower()):
            if pk in used:
                continue
            combined = "{} (0)".format(all_categories[pk])
            category_choices.append((pk, combined))
        self.fields["categories"].choices = category_choices

    def clean_proper_keywords(self):
        value = self.cleaned_data["proper_keywords"]
        return [x.strip() for x in value.splitlines() if x.strip()]

    def clean_oid(self):
        value = self.cleaned_data["oid"]
        filter_ = BlogItem.objects.filter(oid=value)
        if self.instance:
            filter_ = filter_.exclude(oid=self.instance.oid)
        if filter_.exists():
            raise forms.ValidationError("OID already in use")
        return value

    def clean_text(self):
        text = self.cleaned_data["text"]
        if re.findall(r"<!--\s*split\s*-->", text) and "<!--split-->" not in text:
            raise forms.ValidationError(
                "You have a <!-- split --> but not a <!--split-->"
            )
        return text.strip()


class PreviewBlogForm(forms.ModelForm):
    """Exclusively when previewing."""

    class Meta:
        fields = ("text", "display_format")
        model = BlogItem


class EditBlogForm(BlogForm):
    pass


class BlogFileUpload(forms.ModelForm):
    class Meta:
        model = BlogFile
        exclude = ("add_date", "modify_date")


class BlogFileForm(forms.ModelForm):
    class Meta:
        model = BlogFile
        fields = (
            "id",
            "title",
        )


class BlogCommentBatchForm(forms.Form):
    comments = forms.ModelMultipleChoiceField(
        queryset=BlogComment.objects, to_field_name="oid"
    )


class BlogCommentBatchBothForm(forms.Form):
    approve = forms.ModelMultipleChoiceField(
        queryset=BlogComment.objects, to_field_name="oid", required=False
    )
    delete = forms.ModelMultipleChoiceField(
        queryset=BlogComment.objects, to_field_name="oid", required=False
    )

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("approve") and not cleaned_data.get("delete"):
            raise forms.ValidationError("Either approve or delete is required")
        return cleaned_data


class EditBlogCommentForm(forms.ModelForm):
    class Meta:
        model = BlogComment
        fields = ("comment", "name", "email")

    def clean_email(self):
        email = self.cleaned_data["email"]
        if not email:
            return email
        validator = EmailValidator()
        try:
            validator(email)
        except forms.ValidationError:
            raise forms.ValidationError("Invalid email address")
        return email


class BlogitemRealtimeHitsForm(forms.Form):
    since = ISODateTimeField(required=False)
    search = forms.CharField(required=False)


class SpamCommentPatternForm(forms.ModelForm):
    class Meta:
        model = SpamCommentPattern
        fields = ("pattern", "is_regex", "is_url_pattern")


class ProbeURLForm(forms.Form):
    url = forms.URLField()
    method = forms.CharField(required=False)
    user_agent = forms.CharField(required=False)


class CommentCountsForm(forms.Form):
    start = ISODateTimeField()
    end = ISODateTimeField()


class CommentCountsIntervalForm(forms.Form):
    days = forms.CharField(required=False)

    def __init__(self, data, **kwargs):
        initial = kwargs.get("initial", {})
        data = MultiValueDict({**{k: [v] for k, v in initial.items()}, **data})
        super().__init__(data, **kwargs)

    def clean_days(self):
        value = int(self.cleaned_data["days"])
        if value < 1 or value > 365:
            raise forms.ValidationError("Not in [1, 365]")
        return value

    def clean(self):
        cleaned_data = super().clean()
        cleaned_data["end"] = timezone.now()
        cleaned_data["start"] = cleaned_data["end"] - datetime.timedelta(
            days=cleaned_data["days"]
        )
        return cleaned_data


class SpamCommentSignatureForm(forms.Form):
    name = forms.CharField(required=False)
    name_null = forms.BooleanField(required=False)
    email = forms.CharField(required=False)
    email_null = forms.BooleanField(required=False)

    def clean(self):
        cleaned_data = super(SpamCommentSignatureForm, self).clean()

        if not cleaned_data.get("name") and not cleaned_data.get("email"):
            raise forms.ValidationError("Either name or email is required")
        if (not cleaned_data.get("name") and not cleaned_data.get("name_null")) or (
            not cleaned_data.get("email") and not cleaned_data.get("email_null")
        ):
            raise forms.ValidationError("Must be null")

        return cleaned_data


class BlogCommentClassificationForm(forms.ModelForm):
    class Meta:
        model = BlogCommentClassification
        fields = ("text", "classification")

    def clean_classification(self):
        value = self.cleaned_data["classification"]
        return value.lower()


class CategoryForm(forms.Form):
    name = forms.CharField(required=True)
    category = forms.ModelChoiceField(queryset=Category.objects.all(), required=False)


class AllBlogitemsForm(forms.Form):
    since = forms.DateTimeField(required=False)
    minimal_fields = forms.BooleanField(required=False)
