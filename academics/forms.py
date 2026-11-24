from django import forms
from .models import Submission
class SubmissionForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = ["body"]
class GradeForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = ["grade","feedback"]
