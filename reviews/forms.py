from django import forms

from .models import ReviewRating


class ReviewRatingForm(forms.Form):
    rating = forms.ChoiceField(choices=ReviewRating.choices)
    note = forms.CharField(
        required=False,
        max_length=500,
        label="Optional recall note",
        help_text="Capture the one thing that should shape your next revisit.",
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Example: I knew the invariant but missed the left boundary.",
            }
        ),
    )

    def clean_note(self):
        return self.cleaned_data.get("note", "").strip()
