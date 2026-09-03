from django.core.validators import MinValueValidator
from django.db import models


class AssessmentPool(models.Model):
    """The generated Saturday pool for one calendar week."""

    week_start = models.DateField(unique=True)
    requested_problem_count = models.PositiveSmallIntegerField(
        default=3,
        validators=[MinValueValidator(1)],
    )
    duration_minutes = models.PositiveIntegerField(
        default=90,
        validators=[MinValueValidator(1)],
    )
    rationale = models.TextField(blank=True)
    eligibility_metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "assessments"
        ordering = ("-week_start", "-id")

    def __str__(self) -> str:
        return f"Saturday assessment for week of {self.week_start:%Y-%m-%d}"

    @property
    def selected_count(self) -> int:
        return self.selections.count()

    @property
    def is_sparse(self) -> bool:
        return self.selected_count < self.requested_problem_count

    @property
    def mix_label(self) -> str:
        counts = {
            difficulty: self.selections.filter(slot_kind=difficulty).count()
            for difficulty in ("easy", "medium")
        }
        return f"{counts['easy']} easy · {counts['medium']} medium"


class AssessmentSelection(models.Model):
    """One problem selected for a generated Saturday assessment."""

    class SlotKind(models.TextChoices):
        EASY = "easy", "Easy"
        MEDIUM = "medium", "Medium"

    pool = models.ForeignKey(
        AssessmentPool,
        on_delete=models.CASCADE,
        related_name="selections",
    )
    problem = models.ForeignKey(
        "problems.Problem",
        on_delete=models.PROTECT,
        related_name="assessment_selections",
    )
    position = models.PositiveSmallIntegerField()
    slot_kind = models.CharField(max_length=20, choices=SlotKind.choices)
    is_unseen = models.BooleanField(default=True)
    rationale = models.TextField()
    eligibility_metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "assessments"
        ordering = ("position", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("pool", "problem"),
                name="unique_assessment_pool_problem",
            ),
            models.UniqueConstraint(
                fields=("pool", "position"),
                name="unique_assessment_pool_position",
            ),
        ]
        indexes = [
            models.Index(
                fields=("pool", "slot_kind"),
                name="assessments_pool_slot_kind_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.position}. {self.problem.title} in {self.pool}"

    @property
    def concept_labels(self) -> list[str]:
        return [
            concept.get("name", "")
            for concept in self.eligibility_metadata.get("eligible_concepts", [])
            if concept.get("name")
        ]
