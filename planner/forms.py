from django import forms

from curriculum.models import Concept

from .models import StudyBlock


class StudyBlockEditForm(forms.ModelForm):
    """Validate the learner-editable parts of a planned study block."""

    planned_minutes = forms.IntegerField(
        min_value=1,
        error_messages={
            "invalid": "Enter a whole number of minutes.",
            "min_value": "Duration must be a positive number of minutes.",
            "required": "Enter a duration in minutes.",
        },
    )
    assigned_concept = forms.ModelChoiceField(
        queryset=Concept.objects.select_related("topic").order_by(
            "topic__display_order", "order", "id"
        ),
        required=False,
        empty_label="Choose a concept",
        label="Concept",
    )

    class Meta:
        model = StudyBlock
        fields = ("title", "planned_minutes", "assigned_concept")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and not self.instance.is_concept_learning_block:
            self.fields["assigned_concept"].disabled = True

    def save(self, commit=True):
        block = super().save(commit=False)
        if "assigned_concept" in self.changed_data:
            block.concept_assignment_source = (
                StudyBlock.ConceptAssignmentSource.MANUAL
                if block.assigned_concept_id
                else ""
            )
        if commit:
            block.save()
        return block

    def clean_title(self) -> str:
        title = self.cleaned_data["title"].strip()
        if not title:
            raise forms.ValidationError("Give this study block a title.")
        return title


class StopWorkSessionForm(forms.Form):
    """Make block completion an intentional choice when stopping a timer."""

    complete_block = forms.BooleanField(
        required=False,
        label="Mark this study block complete",
    )
