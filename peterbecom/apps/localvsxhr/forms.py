from django import forms

from peterbecom.apps.localvsxhr.models import Measurement


class MeasurementForm(forms.ModelForm):

    class Meta:
        model = Measurement
        exclude = ('add_date',)

        
