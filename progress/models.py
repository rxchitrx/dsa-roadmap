from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class ConceptNote(models.Model):
    """The learner's editable explanation and notes for one Concept."""

    concept = models.OneToOneField(
        "curriculum.Concept",
        on_delete=models.CASCADE,
        related_name="personal_note",
    )
    body = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Notes for {self.concept.name}"


class ConceptCheckpoint(models.Model):
    """An immutable confidence and recall submission for one Concept."""

    class Confidence(models.IntegerChoices):
        NOT_YET = 1, "Not yet confident"
        DEVELOPING = 2, "Developing"
        SOLID = 3, "Solid enough to practice"
        CONFIDENT = 4, "Confident"
        TEACHABLE = 5, "Could teach it"

    concept = models.ForeignKey(
        "curriculum.Concept",
        on_delete=models.CASCADE,
        related_name="checkpoints",
    )
    confidence = models.PositiveSmallIntegerField(
        choices=Confidence.choices,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    recall_response = models.TextField(max_length=2000)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-submitted_at", "-id")

    def __str__(self) -> str:
        return f"{self.concept.name} checkpoint ({self.submitted_at:%Y-%m-%d})"
