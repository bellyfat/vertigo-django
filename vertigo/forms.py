from django import forms
from django.forms import ModelForm
from django.utils import timezone

from .models import EquipmentBorrowing


class EquipmentBorrowingForm(ModelForm):

    def clean(self):
        cleaned_data = super(EquipmentBorrowingForm, self).clean()
        date = cleaned_data.get("date")
        print(date)
        print(timezone.now().date())
        if date > timezone.now().date():
            print(True)
            self.add_error('date', "Tu ne peux pas emrunter dans le futur !")
            # raise forms.ValidationError("Tu ne peux pas emrunter dans le futur !", code='invalid')
        return cleaned_data

    class Meta:
        model = EquipmentBorrowing
        fields = ['date', 'user']
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'user': forms.Select(attrs={'class': 'form-control'}),
        }
