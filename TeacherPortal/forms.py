from django import forms
from .models import Grade
from dashboard.models import Subject, Sections
from decimal import Decimal

class GradeEntryForm(forms.Form):
    def __init__(self, *args, **kwargs):
        students = kwargs.pop('students', None)
        super(GradeEntryForm, self).__init__(*args, **kwargs)
        
        if students:
            self.fields['student'] = forms.ChoiceField(
                choices=[(s.student_id, f"{s.last_name}, {s.first_name}") for s in students],
                widget=forms.Select(attrs={'class': 'form-select'})
            )

class GradeImportForm(forms.Form):
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    quarter = forms.ChoiceField(
        choices=Grade.QUARTER_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    school_year = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    file = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.xlsx,.xls'})
    )

    def __init__(self, *args, **kwargs):
        teacher = kwargs.pop('teacher', None)
        super(GradeImportForm, self).__init__(*args, **kwargs)
        if teacher:
            self.fields['subject'].queryset = Subject.objects.filter(
                schedules__teacher_id=teacher
            ).distinct()