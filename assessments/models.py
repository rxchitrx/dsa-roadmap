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
    def has_fallback(self) -> bool:
        return bool(self.eligibility_metadata.get("fallback_included"))

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

    class SourceKind(models.TextChoices):
        CURRENT_WEEK = "current_week_studied_concept", "Current-week Concept"
        OLDER_CONCEPT_FALLBACK = (
            "older_concept_fallback",
            "Older Concept fallback",
        )

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

    @property
    def source_kind(self) -> str:
        """Return the selection source, including compatibility for old rows."""

        return self.eligibility_metadata.get(
            "source_kind",
            self.SourceKind.CURRENT_WEEK,
        )

    @property
    def source_reason(self) -> str:
        """Explain why this selection came from its source pool."""

        return self.eligibility_metadata.get("source_reason", "")

    @property
    def is_fallback(self) -> bool:
        return self.source_kind == self.SourceKind.OLDER_CONCEPT_FALLBACK


class AssessmentSession(models.Model):
    """A resumable timed attempt against one generated Saturday pool."""

    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In progress"
        OVERTIME = "overtime", "Overtime"
        COMPLETED = "completed", "Completed"

    pool = models.OneToOneField(
        AssessmentPool,
        on_delete=models.CASCADE,
        related_name="session",
    )
    duration_minutes = models.PositiveIntegerField(
        default=90,
        validators=[MinValueValidator(1)],
    )
    started_at = models.DateTimeField()
    cutoff_at = models.DateTimeField()
    cutoff_recorded_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    current_position = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.IN_PROGRESS,
    )
    cutoff_snapshot = models.JSONField(default=dict, blank=True)
    final_summary = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "assessments"
        ordering = ("-started_at", "-id")

    def __str__(self) -> str:
        return f"Assessment session for {self.pool}"

    @property
    def is_editable(self) -> bool:
        return self.status != self.Status.COMPLETED

    @property
    def is_overtime(self) -> bool:
        return self.status == self.Status.OVERTIME


class AssessmentResponse(models.Model):
    """The learner's draft and self-recorded outcome for one Problem."""

    class Outcome(models.TextChoices):
        NOT_STARTED = "not_started", "Not started"
        IN_PROGRESS = "in_progress", "In progress"
        SOLVED = "solved", "Solved"
        NEEDS_REVIEW = "needs_review", "Needs review"
        SKIPPED = "skipped", "Skipped"

    session = models.ForeignKey(
        AssessmentSession,
        on_delete=models.CASCADE,
        related_name="responses",
    )
    selection = models.OneToOneField(
        AssessmentSelection,
        on_delete=models.CASCADE,
        related_name="response",
    )
    draft_answer = models.TextField(blank=True)
    outcome = models.CharField(
        max_length=20,
        choices=Outcome.choices,
        default=Outcome.NOT_STARTED,
    )
    result_note = models.TextField(blank=True)
    cutoff_draft_answer = models.TextField(null=True, blank=True)
    cutoff_outcome = models.CharField(
        max_length=20,
        choices=Outcome.choices,
        null=True,
        blank=True,
    )
    cutoff_result_note = models.TextField(null=True, blank=True)
    cutoff_recorded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "assessments"
        ordering = ("selection__position", "id")
        indexes = [
            models.Index(
                fields=("session", "outcome"),
                name="assess_session_outcome_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"Response for {self.selection.problem.title}"

    @property
    def has_progress(self) -> bool:
        return bool(self.draft_answer.strip()) or self.outcome != self.Outcome.NOT_STARTED
