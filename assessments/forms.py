from django import forms

from .models import AssessmentMistake


class AssessmentMistakeForm(forms.ModelForm):
    class Meta:
        model = AssessmentMistake
        fields = ("cause", "corrected_approach", "next_action")
        labels = {
            "cause": "Root cause",
            "corrected_approach": "Corrected approach",
            "next_action": "Next action",
        }
        help_texts = {
            "cause": "Name the reason this Problem broke down.",
            "corrected_approach": "Write the approach you want to reproduce next time.",
            "next_action": "Choose one concrete follow-up, such as a revisit or a short implementation.",
        }
        widgets = {
            "corrected_approach": forms.Textarea(attrs={"rows": 4}),
            "next_action": forms.Textarea(attrs={"rows": 3}),
        }
