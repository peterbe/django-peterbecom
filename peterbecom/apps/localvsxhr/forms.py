from django import forms

from peterbecom.apps.localvsxhr.models import Measurement


class MeasurementForm(forms.ModelForm):

    class Meta:
        model = Measurement
        exclude = ('add_date',)

    def clean_driver(self):
        value = self.cleaned_data['driver']
        if not value:
            # replace '' with None
            value = None
        return value
