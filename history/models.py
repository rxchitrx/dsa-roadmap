from django.db import models


class RunHistoryEntry(models.Model):
    """An immutable learner-facing snapshot of one visible-test execution."""

    practice_run = models.OneToOneField(
        "practice.PracticeRun",
        on_delete=models.CASCADE,
        related_name="history_entry",
    )
    code_snapshot = models.TextField()
    status = models.CharField(max_length=24)
    result_summary = models.TextField()
    passed_tests = models.PositiveIntegerField(default=0)
    total_tests = models.PositiveIntegerField(default=0)
    duration_ms = models.PositiveIntegerField(default=0)
    captured_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ("-captured_at", "-id")
        indexes = [
            models.Index(fields=("status", "-captured_at")),
        ]

    def __str__(self) -> str:
        return f"{self.practice_run.problem.title} run history ({self.get_status_display()})"

    @property
    def status_label(self) -> str:
        return dict(self.practice_run.Status.choices).get(self.status, self.status)

    @property
    def result_count_label(self) -> str:
        if not self.total_tests:
            return "No visible tests"
        return f"{self.passed_tests} of {self.total_tests} tests passed"

    @classmethod
    def snapshot_for(cls, practice_run):
        """Build a stable snapshot without changing the PracticeRun record."""

        return cls(
            practice_run=practice_run,
            code_snapshot=practice_run.code,
            status=practice_run.status,
            result_summary=practice_run.summary,
            passed_tests=practice_run.passed_tests,
            total_tests=practice_run.total_tests,
            duration_ms=practice_run.duration_ms,
            captured_at=practice_run.created_at,
        )
