from django import forms

from .models import ReviewRating


class SundayReviewBatchForm(forms.Form):
    count = forms.IntegerField(
        min_value=1,
        initial=5,
        label="Problems in this Sunday batch",
        help_text="Choose how many due Problems to revisit today.",
        widget=forms.NumberInput(attrs={"min": 1, "inputmode": "numeric"}),
    )


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
