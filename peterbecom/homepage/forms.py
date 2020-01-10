import copy

from django import forms


class DebugSearchForm(forms.Form):
    q = forms.CharField()
    CHOICES = ("multiply", "sum", "avg")
    popularity_factor = forms.FloatField(required=False)
    boost_mode = forms.ChoiceField(choices=[(x, x) for x in CHOICES], required=False)

    def __init__(self, data, **kwargs):
        data = copy.copy(data)
        for key, value in kwargs.get("initial", {}).items():
            data[key] = data.get(key, value)
        super().__init__(data, **kwargs)
