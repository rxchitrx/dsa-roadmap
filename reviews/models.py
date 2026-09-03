from datetime import timedelta

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models
from django.utils import timezone


class ReviewRating(models.TextChoices):
    """The three fast choices available after recalling a Problem."""

    COULD_NOT_SOLVE = "could_not_solve", "Couldn't solve"
    SOLVED_WITH_HELP = "solved_with_help", "Solved with help"
    SOLVED_INDEPENDENTLY = "solved_independently", "Solved independently"


class ProblemReview(models.Model):
    """The current spaced-review state for one Problem."""

    Rating = ReviewRating

    problem = models.OneToOneField(
        "problems.Problem",
        on_delete=models.CASCADE,
        related_name="problem_review",
    )
    rating = models.CharField(max_length=32, choices=ReviewRating.choices)
    interval_days = models.PositiveIntegerField(default=1)
    due_at = models.DateTimeField(db_index=True)
    review_count = models.PositiveIntegerField(default=1)
    last_reviewed_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("due_at", "problem_id")
        indexes = [
            models.Index(fields=("due_at", "rating")),
        ]

    def __str__(self) -> str:
        return f"{self.problem.title} review due {self.due_at:%Y-%m-%d}"

    @property
    def is_due(self) -> bool:
        return self.due_at <= timezone.now()

    @property
    def due_in_label(self) -> str:
        """Return a compact learner-facing due state."""

        if self.is_due:
            return "Due now"
        return f"Due in {self.interval_days} day{'s' if self.interval_days != 1 else ''}"

    @property
    def is_overdue(self) -> bool:
        """Whether this review was due before the learner's current day."""

        due_date = timezone.localtime(self.due_at).date()
        return due_date < timezone.localdate()

    @property
    def queue_due_label(self) -> str:
        """Return the label used in the learner's due-review queue."""

        return "Overdue" if self.is_overdue else "Due today"

    @property
    def current_learning_status(self):
        """Return the current status without creating an unseen status row."""

        try:
            return self.problem.learning_status
        except ObjectDoesNotExist:
            return None


class ProblemReviewEvent(models.Model):
    """An immutable record of every review rating and resulting schedule."""

    review = models.ForeignKey(
        ProblemReview,
        on_delete=models.CASCADE,
        related_name="history",
    )
    rating = models.CharField(max_length=32, choices=ReviewRating.choices)
    previous_rating = models.CharField(
        max_length=32,
        choices=ReviewRating.choices,
        blank=True,
    )
    previous_interval_days = models.PositiveIntegerField(default=0)
    interval_days = models.PositiveIntegerField()
    reviewed_at = models.DateTimeField(default=timezone.now, db_index=True)
    due_at = models.DateTimeField()
    note = models.CharField(max_length=500, blank=True)
    learning_status_event = models.ForeignKey(
        "practice.LearningStatusEvent",
        on_delete=models.SET_NULL,
        related_name="review_events",
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ("-reviewed_at", "-id")
        indexes = [
            models.Index(fields=("review_id", "-reviewed_at")),
            models.Index(fields=("rating", "-reviewed_at")),
        ]

    def __str__(self) -> str:
        return f"{self.review.problem.title} review ({self.get_rating_display()})"

    def clean(self) -> None:
        valid_ratings = {value for value, _label in ReviewRating.choices}
        if self.rating not in valid_ratings:
            raise ValidationError({"rating": "Choose a valid review rating."})
        if self.interval_days < 1:
            raise ValidationError({"interval_days": "Review interval must be at least one day."})
