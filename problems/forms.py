from django import forms
from django.core.exceptions import ValidationError

from curriculum.models import Concept

from .models import ProblemClassification


class ProblemClassificationForm(forms.ModelForm):
    """Validate one Problem-to-Concept tag before the domain service saves it."""

    class Meta:
        model = ProblemClassification
        fields = ("concept", "status", "note")

    def __init__(self, *args, problem=None, **kwargs):
        self.problem = problem
        super().__init__(*args, **kwargs)
        self.fields["concept"].queryset = Concept.objects.select_related("topic").order_by(
            "topic__display_order", "order", "name", "id"
        )

    def clean(self):
        cleaned_data = super().clean()
        problem = self.problem or getattr(self.instance, "problem", None)
        concept = cleaned_data.get("concept")

        if problem is not None and concept is not None:
            existing = ProblemClassification.objects.filter(
                problem=problem,
                concept=concept,
            ).exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError("This Problem is already classified with that Concept.")

        status = cleaned_data.get("status")
        note = (cleaned_data.get("note") or "").strip()
        if status in {
            ProblemClassification.Status.UNCERTAIN,
            ProblemClassification.Status.FALLBACK,
        } and not note:
            self.add_error(
                "note",
                "Add a reason for an uncertain or fallback classification.",
            )
        cleaned_data["note"] = note
        return cleaned_data
