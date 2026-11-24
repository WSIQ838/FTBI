from django import forms
from .models import Submission
class SubmissionForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = ["body"]
class GradeForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.criteria = list(self.instance.assignment.rubric.all()) if self.instance.pk else []
        if self.criteria:
            del self.fields["grade"]
            for criterion in self.criteria:
                self.fields[f"criterion_{criterion.pk}"] = forms.DecimalField(
                    label=f"{criterion.title} (out of {criterion.points})", min_value=0,
                    max_value=criterion.points, decimal_places=2,
                    initial=self.instance.rubric_scores.get(str(criterion.pk)),
                    help_text=criterion.description,
                )

    def clean(self):
        data = super().clean()
        if self.criteria and all(f"criterion_{c.pk}" in data for c in self.criteria):
            from decimal import Decimal
            self.instance.rubric_scores = {str(c.pk): str(data[f"criterion_{c.pk}"]) for c in self.criteria}
            self.instance.grade = (sum(data[f"criterion_{c.pk}"] for c in self.criteria) * 100 / sum(c.points for c in self.criteria)).quantize(Decimal("0.01"))
        return data

    class Meta:
        model = Submission
        fields = ["grade","feedback"]
