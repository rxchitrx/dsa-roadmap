from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class StudyBlock(models.Model):
    """A planned unit of DSA work for one calendar date."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"

    class ConceptAssignmentSource(models.TextChoices):
        AUTOMATIC = "automatic", "Recommended"
        MANUAL = "manual", "Selected by you"

    date = models.DateField()
    title = models.CharField(max_length=200)
    planned_minutes = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    week_start = models.DateField(blank=True, db_index=True, null=True)
    routine_key = models.CharField(blank=True, max_length=80, null=True)
    assigned_concept = models.ForeignKey(
        "curriculum.Concept",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="study_blocks",
    )
    concept_assignment_source = models.CharField(
        blank=True,
        choices=ConceptAssignmentSource.choices,
        default="",
        max_length=20,
    )
    carried_from = models.ForeignKey(
        "self",
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="carry_forward_blocks",
    )
    position = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("date", "position", "id")
        constraints = [
            models.UniqueConstraint(
                condition=Q(week_start__isnull=False, routine_key__isnull=False),
                fields=("week_start", "routine_key"),
                name="planner_unique_weekly_block_key",
            ),
        ]
        indexes = [models.Index(fields=("date", "status"))]

    def __str__(self) -> str:
        return f"{self.title} ({self.date:%Y-%m-%d})"

    @property
    def is_carried_forward(self) -> bool:
        return self.carried_from_id is not None

    @property
    def is_concept_learning_block(self) -> bool:
        """Whether this row is the routine's learn-one-concept block."""

        return bool(self.routine_key and self.routine_key.endswith("-concept"))

    @property
    def is_problem_solve_block(self) -> bool:
        """Whether this row is a weekday block for solving Problems."""

        return bool(self.routine_key and self.routine_key.endswith("-problems"))


class StudyBlockProblem(models.Model):
    """One Problem assigned to a study block, in learner-facing order."""

    class AssignmentSource(models.TextChoices):
        AUTOMATIC = "automatic", "Auto-filled"
        MANUAL = "manual", "Selected by you"

    study_block = models.ForeignKey(
        StudyBlock,
        on_delete=models.CASCADE,
        related_name="problem_assignments",
    )
    problem = models.ForeignKey(
        "problems.Problem",
        on_delete=models.CASCADE,
        related_name="study_block_assignments",
    )
    position = models.PositiveSmallIntegerField(default=0)
    assignment_source = models.CharField(
        choices=AssignmentSource.choices,
        default=AssignmentSource.AUTOMATIC,
        max_length=20,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("position", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("study_block", "problem"),
                name="planner_unique_block_problem",
            ),
            models.UniqueConstraint(
                fields=("study_block", "position"),
                name="planner_unique_block_problem_position",
            ),
        ]
        indexes = [
            models.Index(fields=("study_block", "position")),
            models.Index(fields=("problem", "study_block")),
        ]

    def __str__(self) -> str:
        return f"{self.study_block.title}: {self.problem.title}"


class RestDay(models.Model):
    """A date intentionally set aside without changing its planned blocks."""

    date = models.DateField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("date", "id")

    def __str__(self) -> str:
        return f"Rest day ({self.date:%Y-%m-%d})"


class WorkSession(models.Model):
    """A learner's persisted timer run for one study block."""

    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        PAUSED = "paused", "Paused"
        STOPPED = "stopped", "Stopped"

    study_block = models.ForeignKey(
        StudyBlock,
        on_delete=models.CASCADE,
        related_name="work_sessions",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RUNNING,
    )
    started_at = models.DateTimeField()
    last_resumed_at = models.DateTimeField()
    paused_at = models.DateTimeField(blank=True, null=True)
    stopped_at = models.DateTimeField(blank=True, null=True)
    elapsed_seconds = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [
            models.UniqueConstraint(
                condition=models.Q(
                    status__in=("running", "paused"),
                ),
                fields=("study_block",),
                name="planner_one_active_work_session_per_block",
            ),
        ]
        indexes = [models.Index(fields=("study_block", "status"))]

    def __str__(self) -> str:
        return f"{self.study_block.title} work session ({self.get_status_display()})"

    @property
    def is_active(self) -> bool:
        return self.status in {self.Status.RUNNING, self.Status.PAUSED}

    def elapsed_seconds_at(self, now=None) -> int:
        """Return elapsed time including an unpersisted, current run segment."""

        if self.status != self.Status.RUNNING or self.last_resumed_at is None:
            return self.elapsed_seconds

        from django.utils import timezone

        current_time = now or timezone.now()
        additional_seconds = max(
            0,
            int((current_time - self.last_resumed_at).total_seconds()),
        )
        return self.elapsed_seconds + additional_seconds
