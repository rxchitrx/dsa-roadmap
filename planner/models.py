from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class StudyBlock(models.Model):
    """A planned unit of DSA work for one calendar date."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"

    date = models.DateField()
    title = models.CharField(max_length=200)
    planned_minutes = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    week_start = models.DateField(blank=True, db_index=True, null=True)
    routine_key = models.CharField(blank=True, max_length=80, null=True)
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
