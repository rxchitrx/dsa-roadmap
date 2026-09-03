from django.core.exceptions import ValidationError
from django.db import models


class ProblemDraft(models.Model):
    """The current local Python draft for one catalog Problem."""

    problem = models.OneToOneField(
        "problems.Problem",
        on_delete=models.CASCADE,
        related_name="python_draft",
    )
    starter_signature = models.CharField(max_length=240)
    code = models.TextField()
    revision = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at", "-id")

    def __str__(self) -> str:
        return f"Python draft for {self.problem.title} (revision {self.revision})"

    @property
    def version(self) -> int:
        """A readable alias for clients that call the counter a version."""

        return self.revision


class CustomTestCase(models.Model):
    """A learner-authored visible test case for one catalog Problem.

    ``input_data`` is a JSON array of positional arguments. Keeping the
    learner's cases as JSON makes the format explicit and lets the isolated
    runner use the same payload shape as the built-in visible tests.
    """

    problem = models.ForeignKey(
        "problems.Problem",
        on_delete=models.CASCADE,
        related_name="custom_practice_tests",
    )
    label = models.CharField(max_length=120)
    input_data = models.JSONField(default=list)
    expected_output = models.JSONField(null=True)
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("position", "created_at", "id")
        indexes = [
            models.Index(fields=("problem", "position")),
        ]

    def __str__(self) -> str:
        return f"Custom test for {self.problem.title}: {self.label}"


class PracticeRun(models.Model):
    """One isolated visible-test execution for a Problem draft."""

    class Status(models.TextChoices):
        PASSED = "passed", "Passed"
        ASSERTION_FAILURE = "assertion_failure", "Assertion failure"
        RUNTIME_ERROR = "runtime_error", "Runtime error"
        TIMEOUT = "timeout", "Timed out"
        SAFETY_VIOLATION = "safety_violation", "Blocked for safety"
        NO_TESTS = "no_tests", "No visible tests"

    problem = models.ForeignKey(
        "problems.Problem",
        on_delete=models.CASCADE,
        related_name="practice_runs",
    )
    code = models.TextField()
    status = models.CharField(max_length=24, choices=Status.choices)
    passed_tests = models.PositiveIntegerField(default=0)
    total_tests = models.PositiveIntegerField(default=0)
    duration_ms = models.PositiveIntegerField(default=0)
    message = models.TextField(blank=True)
    details = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=("problem", "-created_at")),
            models.Index(fields=("status", "-created_at")),
        ]

    def __str__(self) -> str:
        return f"{self.problem.title} practice run ({self.get_status_display()})"

    @property
    def summary(self) -> str:
        if self.status == self.Status.NO_TESTS:
            return "No visible tests are configured for this Problem yet."
        if self.status == self.Status.TIMEOUT:
            return f"Stopped after {self.duration_ms / 1000:.1f}s to protect the workspace."
        if self.total_tests:
            return f"{self.passed_tests} of {self.total_tests} visible tests passed."
        return self.get_status_display()


class SolutionReflection(models.Model):
    """A learner's structured rewrite of one completed practice run."""

    practice_run = models.OneToOneField(
        PracticeRun,
        on_delete=models.CASCADE,
        related_name="reflection",
    )
    rewritten_approach = models.TextField()
    complexity = models.TextField()
    mistake_cause = models.TextField()
    next_correction = models.TextField()
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at", "-id")

    def __str__(self) -> str:
        return f"Reflection for {self.practice_run.problem.title} run #{self.practice_run_id}"

    def clean(self) -> None:
        required_fields = {
            "rewritten_approach": "Write the approach you would use next time.",
            "complexity": "Record the time and space complexity.",
            "mistake_cause": "Name the cause of the mistake or hesitation.",
            "next_correction": "Write one concrete correction for your next attempt.",
        }
        errors = {
            field: message
            for field, message in required_fields.items()
            if not isinstance(getattr(self, field, None), str)
            or not getattr(self, field).strip()
        }
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class LearningStatus(models.TextChoices):
    """The learner's explicit judgment about current problem mastery."""

    UNSEEN = "unseen", "Unseen"
    ATTEMPTED = "attempted", "Attempted — couldn't solve yet"
    SOLVED_WITH_HELP = "solved_with_help", "Solved with help"
    SOLVED_INDEPENDENTLY = "solved_independently", "Solved independently"


class ProblemLearningStatus(models.Model):
    """The current explicit Learning Status for one catalog Problem."""

    Status = LearningStatus

    problem = models.OneToOneField(
        "problems.Problem",
        on_delete=models.CASCADE,
        related_name="learning_status",
    )
    status = models.CharField(
        max_length=32,
        choices=LearningStatus.choices,
        default=LearningStatus.UNSEEN,
    )
    reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at", "-id")

    def __str__(self) -> str:
        return f"{self.problem.title} learning status ({self.get_status_display()})"


class LearningStatusEvent(models.Model):
    """An append-only record of one learner-authored status decision."""

    learning_status = models.ForeignKey(
        ProblemLearningStatus,
        on_delete=models.CASCADE,
        related_name="events",
    )
    problem_snapshot = models.ForeignKey(
        "problems.ProblemSnapshot",
        on_delete=models.PROTECT,
        related_name="learning_status_events",
    )
    practice_run = models.ForeignKey(
        PracticeRun,
        on_delete=models.SET_NULL,
        related_name="learning_status_events",
        blank=True,
        null=True,
    )
    reflection = models.ForeignKey(
        SolutionReflection,
        on_delete=models.SET_NULL,
        related_name="learning_status_events",
        blank=True,
        null=True,
    )
    status = models.CharField(max_length=32, choices=LearningStatus.choices)
    reason = models.TextField()
    changed_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-changed_at", "-id")
        indexes = [
            models.Index(fields=("learning_status", "-changed_at")),
            models.Index(fields=("status", "-changed_at")),
        ]

    def __str__(self) -> str:
        return (
            f"{self.learning_status.problem.title} status event "
            f"({self.get_status_display()})"
        )
