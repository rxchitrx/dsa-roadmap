from django import forms

from .models import ProblemLearningStatus, SolutionReflection


class SolutionReflectionForm(forms.ModelForm):
    """Capture the short rewrite loop that follows a practice run."""

    class Meta:
        model = SolutionReflection
        fields = (
            "rewritten_approach",
            "complexity",
            "mistake_cause",
            "next_correction",
            "notes",
        )
        labels = {
            "rewritten_approach": "Rewritten approach",
            "complexity": "Complexity",
            "mistake_cause": "Mistake or cause",
            "next_correction": "Next correction",
            "notes": "Optional notes",
        }
        help_texts = {
            "rewritten_approach": "Explain the idea in your own words, including the invariant or key decision.",
            "complexity": "Record time and space complexity, and why.",
            "mistake_cause": "What specifically caused the miss: concept, trace, edge case, or implementation?",
            "next_correction": "Choose one action you will take when this pattern appears again.",
            "notes": "Anything else worth preserving for a later revisit.",
        }
        widgets = {
            field: forms.Textarea(attrs={"rows": 5, "class": "reflection-textarea"})
            for field in fields
        }

    def clean(self):
        cleaned_data = super().clean()
        required_fields = {
            "rewritten_approach": "Write the approach you would use next time.",
            "complexity": "Record the time and space complexity.",
            "mistake_cause": "Name the cause of the mistake or hesitation.",
            "next_correction": "Write one concrete correction for your next attempt.",
        }
        for field, message in required_fields.items():
            value = cleaned_data.get(field, "")
            if isinstance(value, str):
                value = value.strip()
                cleaned_data[field] = value
            if not value:
                self.add_error(field, message)

        notes = cleaned_data.get("notes", "")
        if isinstance(notes, str):
            cleaned_data["notes"] = notes.strip()
        return cleaned_data


class LearningStatusForm(forms.ModelForm):
    """Let the learner record a status and the evidence behind the decision."""

    class Meta:
        model = ProblemLearningStatus
        fields = ("status", "reason")
        labels = {
            "status": "Current Learning Status",
            "reason": "Why this status is accurate now",
        }
        help_texts = {
            "status": "This is your judgment, not an automatic interpretation of test results.",
            "reason": "Name the evidence: what you could recall, where you needed help, or what you can now reproduce.",
        }
        widgets = {
            "status": forms.Select(attrs={"class": "learning-status-select"}),
            "reason": forms.Textarea(
                attrs={
                    "rows": 3,
                    "class": "reflection-textarea learning-status-reason",
                    "placeholder": "Example: I could explain the invariant without looking, but needed a hint for the edge case.",
                }
            ),
        }

    def clean_reason(self):
        reason = self.cleaned_data.get("reason", "")
        reason = reason.strip() if isinstance(reason, str) else ""
        if not reason:
            raise forms.ValidationError(
                "Add one short reason so the next revisit has useful context."
            )
        return reason
