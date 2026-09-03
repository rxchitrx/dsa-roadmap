"""Domain analytics for the learner's progress dashboard.

This module intentionally contains no presentation or URL concerns.  It turns
the append-only evidence already captured by the application into a stable,
JSON-friendly shape that a view can render later.

Date filtering is inclusive by local calendar date.  Activity that happens on
the selected start date is included, while activity on the day after the end
date is excluded.  Section-level ``missing_data`` messages are deliberately
part of the result: a zero can mean either "no evidence" or a real zero, and a
learner should be able to tell those cases apart.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.db.models import QuerySet
from django.utils import timezone

from curriculum.models import Concept
from practice.models import (
    LearningStatus,
    LearningStatusEvent,
    PracticeRun,
)
from problems.models import Problem
from progress.models import ConceptCheckpoint
from reviews.models import ProblemReviewEvent, ReviewRating

from .models import StudyBlock, WorkSession


CONCEPT_STATUS_KEYS = {
    ConceptCheckpoint.Confidence.NOT_YET: "not_yet",
    ConceptCheckpoint.Confidence.DEVELOPING: "developing",
    ConceptCheckpoint.Confidence.SOLID: "solid",
    ConceptCheckpoint.Confidence.CONFIDENT: "confident",
    ConceptCheckpoint.Confidence.TEACHABLE: "teachable",
}

_CONCEPT_CONFIDENCE_LABELS = dict(ConceptCheckpoint.Confidence.choices)
CONCEPT_STATUS_LABELS = {
    key: _CONCEPT_CONFIDENCE_LABELS[confidence]
    for confidence, key in CONCEPT_STATUS_KEYS.items()
}


@dataclass(frozen=True)
class AnalyticsRange:
    """An inclusive local-date window and its half-open datetime bounds."""

    start_date: date
    end_date: date

    def __post_init__(self) -> None:
        if self.start_date > self.end_date:
            raise ValueError("Analytics start_date must be on or before end_date.")

    @property
    def days(self) -> int:
        return (self.end_date - self.start_date).days + 1

    @property
    def start_at(self) -> datetime:
        current_timezone = timezone.get_current_timezone()
        return timezone.make_aware(
            datetime.combine(self.start_date, time.min),
            current_timezone,
        )

    @property
    def end_at(self) -> datetime:
        current_timezone = timezone.get_current_timezone()
        return timezone.make_aware(
            datetime.combine(self.end_date + timedelta(days=1), time.min),
            current_timezone,
        )


def _as_date(value: date | datetime | None, *, name: str) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            return timezone.localtime(value).date()
        return value.date()
    if isinstance(value, date):
        return value
    raise TypeError(f"{name} must be a date, datetime, or None.")


def resolve_analytics_range(
    start_date: date | datetime | None = None,
    end_date: date | datetime | None = None,
    *,
    today: date | datetime | None = None,
) -> AnalyticsRange:
    """Resolve an inclusive range, defaulting to the latest 30 local days.

    Supplying only one boundary creates a 30-day window around that boundary.
    This keeps the future analytics route useful with a single query
    parameter while still making both-boundary filtering deterministic.
    """

    start = _as_date(start_date, name="start_date")
    end = _as_date(end_date, name="end_date")
    anchor = _as_date(today, name="today") or timezone.localdate()

    if start is None and end is None:
        end = anchor
        start = end - timedelta(days=29)
    elif start is None:
        start = end - timedelta(days=29)
    elif end is None:
        end = start + timedelta(days=29)

    return AnalyticsRange(start, end)


def _minutes(seconds: int) -> int | float:
    minutes = round(seconds / 60, 1)
    return int(minutes) if minutes.is_integer() else minutes


def _percent(numerator: int, denominator: int) -> float | None:
    if not denominator:
        return None
    return round((numerator / denominator) * 100, 1)


def _date_key(value: datetime) -> date:
    return timezone.localtime(value).date()


def _concept_analytics(window: AnalyticsRange) -> dict:
    concepts = list(
        Concept.objects.select_related("topic").order_by(
            "topic__display_order",
            "topic_id",
            "order",
            "id",
        )
    )
    checkpoints = list(
        ConceptCheckpoint.objects.filter(
            submitted_at__gte=window.start_at,
            submitted_at__lt=window.end_at,
        ).order_by("concept_id", "-submitted_at", "-id")
    )

    latest_by_concept: dict[int, ConceptCheckpoint] = {}
    checkpoint_counts = Counter()
    for checkpoint in checkpoints:
        checkpoint_counts[checkpoint.concept_id] += 1
        latest_by_concept.setdefault(checkpoint.concept_id, checkpoint)

    status_counts = {key: 0 for key in CONCEPT_STATUS_LABELS}
    rows = []
    for concept in concepts:
        latest = latest_by_concept.get(concept.pk)
        status_key = "not_yet" if latest is None else CONCEPT_STATUS_KEYS[latest.confidence]
        if latest is not None:
            status_counts[status_key] += 1
        rows.append(
            {
                "id": concept.pk,
                "topic_id": concept.topic_id,
                "topic": concept.topic.name,
                "name": concept.name,
                "order": concept.order,
                "checkpoint_count": checkpoint_counts[concept.pk],
                "covered": latest is not None,
                "status": status_key,
                "status_label": (
                    CONCEPT_STATUS_LABELS[status_key]
                    if latest is not None
                    else "No checkpoint in selected range"
                ),
                "confidence": latest.confidence if latest is not None else None,
                "confidence_label": (
                    latest.get_confidence_display() if latest is not None else None
                ),
                "latest_checkpoint_at": (
                    latest.submitted_at if latest is not None else None
                ),
                "missing_data": (
                    []
                    if latest is not None
                    else ["No Concept checkpoint was submitted in the selected range."]
                ),
            }
        )

    covered_count = len(latest_by_concept)
    topic_rows = {}
    for row in rows:
        topic = topic_rows.setdefault(
            row["topic_id"],
            {
                "id": row["topic_id"],
                "name": row["topic"],
                "total_count": 0,
                "covered_count": 0,
                "checkpoint_count": 0,
                "status_counts": {key: 0 for key in CONCEPT_STATUS_LABELS},
            },
        )
        topic["total_count"] += 1
        topic["covered_count"] += int(row["covered"])
        topic["checkpoint_count"] += row["checkpoint_count"]
        if row["covered"]:
            topic["status_counts"][row["status"]] += 1
    for topic in topic_rows.values():
        topic["uncovered_count"] = topic["total_count"] - topic["covered_count"]
        topic["coverage_percent"] = _percent(
            topic["covered_count"], topic["total_count"]
        )

    missing_data = []
    if not concepts:
        missing_data.append(
            "No Concepts are seeded, so Concept coverage cannot be calculated."
        )
    elif not checkpoints:
        missing_data.append(
            "No Concept checkpoints were submitted in the selected date range."
        )

    return {
        "total_count": len(concepts),
        "covered_count": covered_count,
        "uncovered_count": len(concepts) - covered_count,
        "coverage_percent": _percent(covered_count, len(concepts)),
        "checkpoint_count": len(checkpoints),
        "status_counts": status_counts,
        "status_labels": CONCEPT_STATUS_LABELS,
        "by_topic": list(topic_rows.values()),
        "by_concept": rows,
        "missing_data": missing_data,
    }


def _problem_analytics(window: AnalyticsRange) -> dict:
    runs = PracticeRun.objects.filter(
        created_at__gte=window.start_at,
        created_at__lt=window.end_at,
    )
    run_status_counts = {
        status: runs.filter(status=status).count()
        for status, _label in PracticeRun.Status.choices
    }
    attempted_problem_ids = set(runs.values_list("problem_id", flat=True))
    passing_problem_ids = set(
        runs.filter(status=PracticeRun.Status.PASSED).values_list(
            "problem_id", flat=True
        )
    )

    status_events = list(
        LearningStatusEvent.objects.filter(
            changed_at__gte=window.start_at,
            changed_at__lt=window.end_at,
        )
        .select_related("learning_status")
        .order_by("learning_status__problem_id", "-changed_at", "-id")
    )
    latest_status_by_problem = {}
    for event in status_events:
        latest_status_by_problem.setdefault(event.learning_status.problem_id, event)

    status_counts = {status: 0 for status, _label in LearningStatus.choices}
    for event in latest_status_by_problem.values():
        status_counts[event.status] += 1

    outcomes = {
        # Attempted and passing are unique Problems in the selected range's
        # practice runs.  The two explicit mastery outcomes come from the
        # latest status event for each Problem in the same range.
        "attempted": len(attempted_problem_ids),
        "passing": len(passing_problem_ids),
        "solved_with_help": status_counts[LearningStatus.SOLVED_WITH_HELP],
        "solved_independently": status_counts[
            LearningStatus.SOLVED_INDEPENDENTLY
        ],
    }

    missing_data = []
    if not runs.exists():
        missing_data.append(
            "No practice runs were recorded in the selected date range; attempted and passing counts are unavailable."
        )
    if not status_events:
        missing_data.append(
            "No explicit Problem Learning Status decisions were recorded in the selected date range; mastery outcomes are unavailable."
        )

    return {
        "catalog_problem_count": Problem.objects.count(),
        "active_problem_count": Problem.objects.filter(is_active=True).count(),
        "practice_run_count": runs.count(),
        "run_status_counts": run_status_counts,
        "learning_status_event_count": len(status_events),
        "learning_status_counts": status_counts,
        "outcomes": outcomes,
        "missing_data": missing_data,
    }


def _review_analytics(window: AnalyticsRange) -> dict:
    events = ProblemReviewEvent.objects.filter(
        reviewed_at__gte=window.start_at,
        reviewed_at__lt=window.end_at,
    )
    rating_counts = {
        rating: events.filter(rating=rating).count()
        for rating, _label in ReviewRating.choices
    }
    total = events.count()
    independent_count = rating_counts[ReviewRating.SOLVED_INDEPENDENTLY]
    assisted_count = rating_counts[ReviewRating.SOLVED_WITH_HELP]
    unique_problem_count = events.values("review__problem_id").distinct().count()

    per_day = {
        window.start_date + timedelta(days=offset): {
            "date": window.start_date + timedelta(days=offset),
            "review_count": 0,
            "independent_count": 0,
            "assisted_count": 0,
            "could_not_solve_count": 0,
        }
        for offset in range(window.days)
    }
    for event in events.only("rating", "reviewed_at"):
        row = per_day[_date_key(event.reviewed_at)]
        row["review_count"] += 1
        if event.rating == ReviewRating.SOLVED_INDEPENDENTLY:
            row["independent_count"] += 1
        elif event.rating == ReviewRating.SOLVED_WITH_HELP:
            row["assisted_count"] += 1
        elif event.rating == ReviewRating.COULD_NOT_SOLVE:
            row["could_not_solve_count"] += 1

    missing_data = []
    if not total:
        missing_data.append(
            "No review ratings were recorded in the selected date range, so retention rates cannot be calculated."
        )

    return {
        "review_count": total,
        "unique_problem_count": unique_problem_count,
        "rating_counts": rating_counts,
        "independent_recall_count": independent_count,
        "successful_recall_count": independent_count + assisted_count,
        "independent_retention_percent": _percent(independent_count, total),
        "successful_recall_percent": _percent(independent_count + assisted_count, total),
        "by_day": list(per_day.values()),
        "missing_data": missing_data,
    }


def _time_analytics(window: AnalyticsRange) -> dict:
    completed_sessions = WorkSession.objects.filter(
        status=WorkSession.Status.STOPPED,
        stopped_at__gte=window.start_at,
        stopped_at__lt=window.end_at,
    )
    seconds_by_day = defaultdict(int)
    sessions_by_day = Counter()
    for session in completed_sessions.only("stopped_at", "elapsed_seconds"):
        day = _date_key(session.stopped_at)
        seconds_by_day[day] += session.elapsed_seconds
        sessions_by_day[day] += 1

    by_day = []
    for offset in range(window.days):
        current_date = window.start_date + timedelta(days=offset)
        seconds = seconds_by_day[current_date]
        by_day.append(
            {
                "date": current_date,
                "session_count": sessions_by_day[current_date],
                "seconds": seconds,
                "minutes": _minutes(seconds),
            }
        )

    active_sessions = WorkSession.objects.filter(
        status__in=(WorkSession.Status.RUNNING, WorkSession.Status.PAUSED),
        started_at__gte=window.start_at,
        started_at__lt=window.end_at,
    ).count()
    missing_data = []
    if not completed_sessions.exists():
        missing_data.append(
            "No completed Work Sessions were logged in the selected range. Running or paused timers are excluded until stopped."
        )
    if active_sessions:
        missing_data.append(
            f"{active_sessions} Work Session{' is' if active_sessions == 1 else 's are'} still running or paused and is not included in completed time."
        )

    total_seconds = sum(seconds_by_day.values())
    return {
        "completed_session_count": completed_sessions.count(),
        "completed_seconds": total_seconds,
        "completed_minutes": _minutes(total_seconds),
        "by_day": by_day,
        "active_session_count": active_sessions,
        "missing_data": missing_data,
    }


def _activity_dates(queryset: QuerySet, field: str, window: AnalyticsRange) -> list[date]:
    """Convert a datetime field from a filtered queryset to local dates."""

    return [
        _date_key(value)
        for value in queryset.values_list(field, flat=True)
        if value is not None
    ]


def _consistency_analytics(window: AnalyticsRange) -> dict:
    activity_by_day = Counter()
    source_counts = Counter()

    sources = (
        (
            "completed_work_sessions",
            WorkSession.objects.filter(
                status=WorkSession.Status.STOPPED,
                stopped_at__gte=window.start_at,
                stopped_at__lt=window.end_at,
            ),
            "stopped_at",
        ),
        (
            "practice_runs",
            PracticeRun.objects.filter(
                created_at__gte=window.start_at,
                created_at__lt=window.end_at,
            ),
            "created_at",
        ),
        (
            "concept_checkpoints",
            ConceptCheckpoint.objects.filter(
                submitted_at__gte=window.start_at,
                submitted_at__lt=window.end_at,
            ),
            "submitted_at",
        ),
        (
            "learning_status_events",
            LearningStatusEvent.objects.filter(
                changed_at__gte=window.start_at,
                changed_at__lt=window.end_at,
            ),
            "changed_at",
        ),
        (
            "review_events",
            ProblemReviewEvent.objects.filter(
                reviewed_at__gte=window.start_at,
                reviewed_at__lt=window.end_at,
            ),
            "reviewed_at",
        ),
    )
    for source_name, queryset, field in sources:
        dates = _activity_dates(queryset, field, window)
        source_counts[source_name] = len(dates)
        activity_by_day.update(dates)

    daily = []
    active_dates = []
    for offset in range(window.days):
        current_date = window.start_date + timedelta(days=offset)
        evidence_count = activity_by_day[current_date]
        if evidence_count:
            active_dates.append(current_date)
        daily.append(
            {
                "date": current_date,
                "active": bool(evidence_count),
                "evidence_count": evidence_count,
            }
        )

    active_date_set = set(active_dates)
    current_streak = 0
    cursor = window.end_date
    while cursor in active_date_set:
        current_streak += 1
        cursor -= timedelta(days=1)

    longest_streak = 0
    running_streak = 0
    for row in daily:
        if row["active"]:
            running_streak += 1
            longest_streak = max(longest_streak, running_streak)
        else:
            running_streak = 0

    missing_data = []
    if not active_dates:
        missing_data.append(
            "No learning activity was recorded in the selected range, so streak and consistency are unavailable."
        )

    return {
        "range_days": window.days,
        "active_day_count": len(active_dates),
        "consistency_percent": _percent(len(active_dates), window.days),
        "current_streak_days": current_streak,
        "longest_streak_days": longest_streak,
        "active_dates": active_dates,
        "activity_sources": dict(source_counts),
        "by_day": daily,
        "missing_data": missing_data,
    }


def get_progress_analytics(
    start_date: date | datetime | None = None,
    end_date: date | datetime | None = None,
    *,
    today: date | datetime | None = None,
) -> dict:
    """Build the complete domain analytics payload for a date range.

    The four sections intentionally use the timestamp that represents the
    evidence being measured:

    * Concept coverage: checkpoint submission time.
    * Problem outcomes: practice-run creation and Learning Status event time.
    * Review retention: review rating time.
    * Completed time: Work Session stop time.

    This makes filtering predictable even when a Work Session's planned block
    date or a Problem's catalog metadata belongs to another week.
    """

    window = resolve_analytics_range(start_date, end_date, today=today)
    sections = {
        "concepts": _concept_analytics(window),
        "problems": _problem_analytics(window),
        "reviews": _review_analytics(window),
        "time": _time_analytics(window),
        "consistency": _consistency_analytics(window),
    }
    missing_data = []
    for section in sections.values():
        for message in section["missing_data"]:
            if message not in missing_data:
                missing_data.append(message)

    return {
        "range": {
            "start_date": window.start_date,
            "end_date": window.end_date,
            "days": window.days,
        },
        **sections,
        "has_data": any(not section["missing_data"] for section in sections.values()),
        "missing_data": missing_data,
    }


# A short alias keeps the service convenient for a future view or API adapter
# without making the more explicit public name disappear.
get_analytics = get_progress_analytics
