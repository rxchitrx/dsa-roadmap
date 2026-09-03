from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from practice.models import LearningStatus, LearningStatusEvent
from practice.services import set_learning_status
from problems.models import Problem

from .models import ProblemReview, ProblemReviewEvent, ReviewRating


FIRST_INTERVALS = {
    ReviewRating.COULD_NOT_SOLVE: 1,
    ReviewRating.SOLVED_WITH_HELP: 3,
    ReviewRating.SOLVED_INDEPENDENTLY: 7,
}

LEARNING_STATUS_FOR_RATING = {
    ReviewRating.COULD_NOT_SOLVE: LearningStatus.ATTEMPTED,
    ReviewRating.SOLVED_WITH_HELP: LearningStatus.SOLVED_WITH_HELP,
    ReviewRating.SOLVED_INDEPENDENTLY: LearningStatus.SOLVED_INDEPENDENTLY,
}


@dataclass(frozen=True)
class ReviewSchedule:
    """The values calculated before they are persisted."""

    interval_days: int
    reviewed_at: datetime
    due_at: datetime


def _validate_rating(rating: str) -> str:
    valid_ratings = {value for value, _label in ReviewRating.choices}
    if rating not in valid_ratings:
        raise ValidationError({"rating": "Choose one of the three review ratings."})
    return rating


def calculate_schedule(
    rating: str,
    *,
    previous_interval_days: int = 0,
    reviewed_at: datetime | None = None,
) -> ReviewSchedule:
    """Calculate a predictable first or repeat interval.

    The first pass is deliberately small and explainable while leaving room
    for a later FSRS parameter layer. A failed recall returns tomorrow, help
    returns in three days (or grows by 1.5x), and independent recall returns
    in seven days (or grows by 2x).
    """

    rating = _validate_rating(rating)
    if previous_interval_days < 0:
        raise ValidationError("Previous review interval cannot be negative.")

    if previous_interval_days == 0:
        interval_days = FIRST_INTERVALS[rating]
    elif rating == ReviewRating.COULD_NOT_SOLVE:
        interval_days = 1
    elif rating == ReviewRating.SOLVED_WITH_HELP:
        interval_days = max(3, math.ceil(previous_interval_days * 1.5))
    else:
        interval_days = max(7, previous_interval_days * 2)

    reviewed_at = reviewed_at or timezone.now()
    return ReviewSchedule(
        interval_days=interval_days,
        reviewed_at=reviewed_at,
        due_at=reviewed_at + timedelta(days=interval_days),
    )


def _status_reason(rating: str, note: str) -> str:
    label = dict(ReviewRating.choices)[rating]
    return note.strip() if note.strip() else f"Review rating: {label}."


@transaction.atomic
def record_review(
    problem: Problem,
    *,
    rating: str,
    note: str = "",
    reviewed_at: datetime | None = None,
) -> tuple[ProblemReview, ProblemReviewEvent]:
    """Record a learner rating and advance one Problem's review schedule."""

    if not isinstance(problem, Problem):
        raise TypeError("problem must be a Problem instance")
    if not problem.pk:
        raise ValidationError("Save the Problem before scheduling a review.")
    if not problem.is_active:
        raise ValidationError("Inactive Problems cannot be scheduled for review.")
    rating = _validate_rating(rating)
    note = note.strip() if isinstance(note, str) else ""
    if len(note) > 500:
        raise ValidationError({"note": "Keep the review note to 500 characters or fewer."})

    review, _created = ProblemReview.objects.select_for_update().get_or_create(
        problem=problem,
        defaults={
            "rating": rating,
            "interval_days": FIRST_INTERVALS[rating],
            "due_at": (reviewed_at or timezone.now())
            + timedelta(days=FIRST_INTERVALS[rating]),
            "review_count": 0,
            "last_reviewed_at": reviewed_at or timezone.now(),
        },
    )
    # A newly created row is locked by the insert, but its first event still
    # needs to use the same explicit scheduling calculation as repeat reviews.
    previous_rating = review.rating if review.review_count else ""
    previous_interval_days = review.interval_days if review.review_count else 0
    schedule = calculate_schedule(
        rating,
        previous_interval_days=previous_interval_days,
        reviewed_at=reviewed_at,
    )

    status_event = _record_learning_status(problem, rating=rating, note=note)
    event = ProblemReviewEvent.objects.create(
        review=review,
        rating=rating,
        previous_rating=previous_rating,
        previous_interval_days=previous_interval_days,
        interval_days=schedule.interval_days,
        reviewed_at=schedule.reviewed_at,
        due_at=schedule.due_at,
        note=note,
        learning_status_event=status_event,
    )
    review.rating = rating
    review.interval_days = schedule.interval_days
    review.due_at = schedule.due_at
    review.review_count += 1
    review.last_reviewed_at = schedule.reviewed_at
    review.save(
        update_fields=(
            "rating",
            "interval_days",
            "due_at",
            "review_count",
            "last_reviewed_at",
            "updated_at",
        )
    )
    return review, event


def _record_learning_status(
    problem: Problem,
    *,
    rating: str,
    note: str,
) -> LearningStatusEvent:
    status, event = set_learning_status(
        problem,
        status=LEARNING_STATUS_FOR_RATING[rating],
        reason=_status_reason(rating, note),
    )
    return event


def review_history(problem: Problem):
    """Return the append-only review journal in newest-first order."""

    return ProblemReviewEvent.objects.filter(review__problem=problem).select_related(
        "review",
        "learning_status_event",
    )
