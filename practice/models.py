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
