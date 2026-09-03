from django import forms

from .models import ConceptCheckpoint, ConceptNote


class ConceptNoteForm(forms.ModelForm):
    class Meta:
        model = ConceptNote
        fields = ("body",)
        labels = {"body": "Your explanation and notes"}
        widgets = {
            "body": forms.Textarea(
                attrs={
                    "rows": 11,
                    "placeholder": "Explain the idea in your own words. Add invariants, examples, or traps you want to remember.",
                }
            )
        }

    def clean_body(self):
        return self.cleaned_data["body"].strip()


class ConceptCheckpointForm(forms.ModelForm):
    class Meta:
        model = ConceptCheckpoint
        fields = ("confidence", "recall_response")
        labels = {
            "confidence": "How confident are you right now?",
            "recall_response": "Recall it without looking",
        }
        widgets = {
            "confidence": forms.Select(),
            "recall_response": forms.Textarea(
                attrs={
                    "rows": 7,
                    "placeholder": "What is the core idea, invariant, or first implementation step?",
                }
            ),
        }

    def clean_recall_response(self):
        response = self.cleaned_data["recall_response"].strip()
        if not response:
            raise forms.ValidationError("Write a short recall response before submitting.")
        return response
