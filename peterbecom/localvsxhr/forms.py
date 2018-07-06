from django import forms

from peterbecom.localvsxhr.models import Measurement, BootMeasurement


class MeasurementForm(forms.ModelForm):
    class Meta:
        model = Measurement
        exclude = ("add_date",)

    def clean_driver(self):
        value = self.cleaned_data["driver"]
        if not value:
            # replace '' with None
            value = None
        return value


class BootMeasurementForm(forms.ModelForm):
    class Meta:
        model = BootMeasurement
        exclude = ("add_date",)
