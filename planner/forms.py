from django import forms

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

    class Meta:
        model = StudyBlock
        fields = ("title", "planned_minutes")

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
