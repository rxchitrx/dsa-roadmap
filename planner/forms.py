from django import forms
from django.db.models import Q

from curriculum.models import Concept
from problems.models import Problem

from .models import StudyBlock, StudyBlockProblem


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
        if self.instance and self.instance.is_problem_solve_block:
            existing_problem_ids = list(
                StudyBlockProblem.objects.filter(study_block=self.instance).values_list(
                    "problem_id", flat=True
                )
            )
            self.fields["assigned_problems"] = forms.ModelMultipleChoiceField(
                queryset=Problem.objects.filter(
                    Q(is_active=True) | Q(pk__in=existing_problem_ids)
                ).order_by("display_order", "title", "id"),
                required=False,
                label="Problems",
                widget=forms.SelectMultiple(
                    attrs={
                        "data-testid": "assigned-problems-input",
                        "size": 5,
                    }
                ),
                help_text="Choose up to two. Leave this unchanged to keep auto-filled Problems.",
            )
            self.initial["assigned_problems"] = existing_problem_ids

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
            # A marker lets the UI intentionally clear every Problem while
            # direct callers that only edit title/duration preserve assignments.
            manages_problems = self.is_bound and (
                "manage_problems" in self.data or "assigned_problems" in self.data
            )
            if manages_problems and "assigned_problems" in self.fields:
                from .services import set_manual_problem_assignments

                set_manual_problem_assignments(
                    block,
                    list(self.cleaned_data.get("assigned_problems", [])),
                )
        return block

    def clean_title(self) -> str:
        title = self.cleaned_data["title"].strip()
        if not title:
            raise forms.ValidationError("Give this study block a title.")
        return title

    def clean_assigned_problems(self):
        problems = self.cleaned_data.get("assigned_problems", [])
        if len(problems) > 2:
            raise forms.ValidationError("Choose at most two Problems for this block.")
        return problems


class StopWorkSessionForm(forms.Form):
    """Make block completion an intentional choice when stopping a timer."""

    complete_block = forms.BooleanField(
        required=False,
        label="Mark this study block complete",
    )
