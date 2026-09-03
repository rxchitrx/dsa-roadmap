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
