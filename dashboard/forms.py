from django import forms
from .models import Registrar

class RegistrarAssignmentForm(forms.ModelForm):
    class Meta:
        model = Registrar
        fields = ['teacher']
        widgets = {
            'teacher': forms.Select(attrs={'class': 'form-control'}),
        }