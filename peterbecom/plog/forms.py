import datetime

from django import forms


class CalendarDataForm(forms.Form):
    start = forms.DateTimeField()
    end = forms.DateTimeField()

    def clean(self):
        cleaned_data = super(CalendarDataForm, self).clean()
        if "start" in cleaned_data and "end" in cleaned_data:
            if cleaned_data["start"] > cleaned_data["end"]:
                raise forms.ValidationError("start > end")
            diff = cleaned_data["end"] - cleaned_data["start"]
            if diff > datetime.timedelta(days=50):
                raise forms.ValidationError("> 50 days")
        return cleaned_data
