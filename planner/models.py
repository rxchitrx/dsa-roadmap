from django.core.validators import MinValueValidator
from django.db import models


class StudyBlock(models.Model):
    """A planned unit of DSA work for one calendar date."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"

    date = models.DateField()
    title = models.CharField(max_length=200)
    planned_minutes = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("date", "id")
        indexes = [models.Index(fields=("date", "status"))]

    def __str__(self) -> str:
        return f"{self.title} ({self.date:%Y-%m-%d})"
