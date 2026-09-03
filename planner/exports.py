"""Import-friendly CSV exports for one planner week.

The export deliberately uses one rectangular schema instead of separate CSV
sections with different headers.  Every row therefore has the same columns,
which keeps the file safe to open in a spreadsheet or load with
``csv.DictReader`` when one of the evidence sections is empty.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from datetime import date, datetime, time, timedelta

from django.db.models import Sum
from django.utils import timezone

from assessments.models import (
    AssessmentMistake,
    AssessmentResponse,
    AssessmentSelection,
    AssessmentSession,
)
from assessments.services import get_assessment_summary
from practice.models import PracticeRun
from reviews.models import ProblemReview, ProblemReviewEvent, ReviewRating

from .models import StudyBlock, WorkSession
from .services import week_start_for
from .summary import _block_type_label


# Stable machine-readable names make the file easy to import, while the
# names still describe the learner-facing meaning of each value.
CSV_HEADERS = (
    "record_type",
    "week_start",
    "week_end",
    "date",
    "day",
    "block_type",
    "title",
    "status",
    "status_label",
    "planned_minutes",
    "completed_seconds",
    "completed_minutes",
    "completed_block",
    "problem_id",
    "problem_slug",
    "problem_title",
    "review_rating",
    "review_rating_label",
    "reviewed_at",
    "review_due_at",
    "practice_status",
    "practice_status_label",
    "practice_passed_tests",
    "practice_total_tests",
    "practice_duration_ms",
    "assessment_status",
    "assessment_status_label",
    "assessment_position",
    "assessment_slot",
    "assessment_source",
    "assessment_source_label",
    "assessment_source_reason",
    "assessment_cutoff_outcome",
    "assessment_cutoff_outcome_label",
    "assessment_final_outcome",
    "assessment_final_outcome_label",
    "summary_metric",
    "summary_metric_label",
    "summary_value",
    "notes",
)


def _as_local_date(value: date | datetime | None, *, name: str) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return timezone.localtime(value).date() if timezone.is_aware(value) else value.date()
    if isinstance(value, date):
        return value
    raise TypeError(f"{name} must be a date, datetime, or None.")


def _selected_week_start(selected_date: date | datetime | None) -> date:
    """Normalize any selected calendar date to its Monday week boundary."""

    value = _as_local_date(selected_date, name="selected_date")
    return week_start_for(value or timezone.localdate())


def _week_bounds(week_start: date) -> tuple[date, date, datetime, datetime]:
    week_end = week_start + timedelta(days=6)
    current_timezone = timezone.get_current_timezone()
    start_at = timezone.make_aware(datetime.combine(week_start, time.min), current_timezone)
    end_at = start_at + timedelta(days=7)
    return week_end, start_at, end_at


def _csv_value(value) -> str:
    """Convert model values to stable, non-``None`` CSV values."""

    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _minutes(seconds: int) -> int | float:
    minutes = round(seconds / 60, 1)
    return int(minutes) if minutes.is_integer() else minutes


def _local_iso(value: datetime | None) -> str:
    if value is None:
        return ""
    if timezone.is_aware(value):
        value = timezone.localtime(value)
    return value.isoformat()


def _empty_row(record_type: str, week_start: date, week_end: date) -> dict[str, str]:
    return {
        header: "" for header in CSV_HEADERS
    } | {
        "record_type": record_type,
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
    }


def _review_label(rating: str | None) -> str:
    return dict(ReviewRating.choices).get(rating, "")


def _assessment_outcome_label(outcome: str | None) -> str:
    return dict(AssessmentResponse.Outcome.choices).get(outcome, "")


def _assessment_source_label(source: str | None) -> str:
    return dict(AssessmentSelection.SourceKind.choices).get(source, "")


def _completed_seconds_by_block(block_ids: Iterable[int]) -> dict[int, int]:
    return {
        row["study_block_id"]: row["total"] or 0
        for row in WorkSession.objects.filter(
            study_block_id__in=list(block_ids),
            status=WorkSession.Status.STOPPED,
        )
        .values("study_block_id")
        .annotate(total=Sum("elapsed_seconds"))
    }


def _routine_rows(
    week_start: date,
    week_end: date,
) -> tuple[list[dict[str, str]], dict[str, int]]:
    blocks = list(
        StudyBlock.objects.filter(date__range=(week_start, week_end)).order_by(
            "date", "position", "id"
        )
    )
    seconds_by_block = _completed_seconds_by_block(block.pk for block in blocks)
    rows = []
    completed_seconds = 0
    completed_block_count = 0
    for block in blocks:
        seconds = seconds_by_block.get(block.pk, 0)
        completed_seconds += seconds
        completed_block_count += block.status == StudyBlock.Status.COMPLETED
        row = _empty_row("routine_block", week_start, week_end)
        row.update(
            {
                "date": block.date.isoformat(),
                "day": block.date.strftime("%A"),
                "block_type": _block_type_label(block),
                "title": block.title,
                "status": block.status,
                "status_label": block.get_status_display(),
                "planned_minutes": _csv_value(block.planned_minutes),
                "completed_seconds": _csv_value(seconds),
                "completed_minutes": _csv_value(_minutes(seconds)),
                "completed_block": _csv_value(
                    block.status == StudyBlock.Status.COMPLETED
                ),
            }
        )
        rows.append(row)

    totals = {
        "planned_minutes": sum(block.planned_minutes for block in blocks),
        "completed_seconds": completed_seconds,
        "completed_minutes": _minutes(completed_seconds),
        "block_count": len(blocks),
        "completed_block_count": completed_block_count,
        "pending_block_count": len(blocks) - completed_block_count,
        "carried_forward_count": sum(block.is_carried_forward for block in blocks),
    }
    return rows, totals


def _review_rows(
    week_start: date,
    week_end: date,
    start_at: datetime,
    end_at: datetime,
) -> list[dict[str, str]]:
    events = (
        ProblemReviewEvent.objects.filter(
            reviewed_at__gte=start_at,
            reviewed_at__lt=end_at,
        )
        .select_related("review__problem")
        .order_by("reviewed_at", "id")
    )
    rows = []
    for event in events:
        reviewed_date = timezone.localtime(event.reviewed_at).date()
        row = _empty_row("review", week_start, week_end)
        row.update(
            {
                "date": reviewed_date.isoformat(),
                "day": reviewed_date.strftime("%A"),
                "title": event.review.problem.title,
                "status": "completed",
                "status_label": "Completed",
                "problem_id": _csv_value(event.review.problem_id),
                "problem_slug": event.review.problem.slug,
                "problem_title": event.review.problem.title,
                "review_rating": event.rating,
                "review_rating_label": _review_label(event.rating),
                "reviewed_at": _local_iso(event.reviewed_at),
                "review_due_at": _local_iso(event.due_at),
                "notes": event.note,
            }
        )
        rows.append(row)
    return rows


def _practice_rows(
    week_start: date,
    week_end: date,
    start_at: datetime,
    end_at: datetime,
) -> list[dict[str, str]]:
    runs = (
        PracticeRun.objects.filter(created_at__gte=start_at, created_at__lt=end_at)
        .select_related("problem")
        .order_by("created_at", "id")
    )
    rows = []
    for run in runs:
        created_date = timezone.localtime(run.created_at).date()
        row = _empty_row("practice_run", week_start, week_end)
        row.update(
            {
                "date": created_date.isoformat(),
                "day": created_date.strftime("%A"),
                "title": run.problem.title,
                "status": run.status,
                "status_label": run.get_status_display(),
                "problem_id": _csv_value(run.problem_id),
                "problem_slug": run.problem.slug,
                "problem_title": run.problem.title,
                "practice_status": run.status,
                "practice_status_label": run.get_status_display(),
                "practice_passed_tests": _csv_value(run.passed_tests),
                "practice_total_tests": _csv_value(run.total_tests),
                "practice_duration_ms": _csv_value(run.duration_ms),
                "notes": run.message or run.summary,
            }
        )
        rows.append(row)
    return rows


def _assessment_rows(
    week_start: date,
    week_end: date,
) -> tuple[list[dict[str, str]], dict[str, int | str]]:
    session = (
        AssessmentSession.objects.select_related("pool")
        .filter(pool__week_start=week_start)
        .first()
    )
    totals: dict[str, int | str] = {
        "assessment_present": 0,
        "assessment_timed_solved": 0,
        "assessment_timed_total": 0,
        "assessment_final_solved": 0,
        "assessment_final_total": 0,
        "assessment_timed_fallback_solved": 0,
        "assessment_timed_fallback_total": 0,
        "assessment_final_fallback_solved": 0,
        "assessment_final_fallback_total": 0,
        "assessment_mistake_total": 0,
        "assessment_mistake_incomplete": 0,
        "assessment_status": "",
    }
    if session is None:
        return [], totals

    summary = get_assessment_summary(session)
    timed = summary.get("timed", {})
    final = summary.get("final", {})
    timed_fallback = timed.get("fallback", {})
    final_fallback = final.get("fallback", {})
    totals.update(
        {
            "assessment_present": 1,
            "assessment_timed_solved": timed.get("solved", 0),
            "assessment_timed_total": timed.get("total", 0),
            "assessment_final_solved": final.get("solved", 0),
            "assessment_final_total": final.get("total", 0),
            "assessment_timed_fallback_solved": timed_fallback.get("solved", 0),
            "assessment_timed_fallback_total": timed_fallback.get("total", 0),
            "assessment_final_fallback_solved": final_fallback.get("solved", 0),
            "assessment_final_fallback_total": final_fallback.get("total", 0),
            "assessment_mistake_total": AssessmentMistake.objects.filter(
                assessment=session
            ).count(),
            "assessment_mistake_incomplete": AssessmentMistake.objects.filter(
                assessment=session,
                is_complete=False,
            ).count(),
            "assessment_status": session.status,
        }
    )

    cutoff_by_selection = {
        row.get("selection_id"): row
        for row in session.cutoff_snapshot.get("responses", [])
    }
    responses_by_selection = {
        response.selection_id: response
        for response in session.responses.all()
    }
    selections = session.pool.selections.select_related("problem").order_by(
        "position", "id"
    )
    rows = []
    assessment_date = week_start + timedelta(days=5)
    for selection in selections:
        response = responses_by_selection.get(selection.pk)
        cutoff = cutoff_by_selection.get(selection.pk, {})
        final_outcome = (
            response.outcome
            if response is not None
            else AssessmentResponse.Outcome.NOT_STARTED
        )
        cutoff_outcome = cutoff.get("outcome") or ""
        row = _empty_row("assessment_response", week_start, week_end)
        row.update(
            {
                "date": assessment_date.isoformat(),
                "day": assessment_date.strftime("%A"),
                "title": selection.problem.title,
                "status": session.status,
                "status_label": session.get_status_display(),
                "problem_id": _csv_value(selection.problem_id),
                "problem_slug": selection.problem.slug,
                "problem_title": selection.problem.title,
                "assessment_status": session.status,
                "assessment_status_label": session.get_status_display(),
                "assessment_position": _csv_value(selection.position),
                "assessment_slot": selection.slot_kind,
                "assessment_source": selection.source_kind,
                "assessment_source_label": _assessment_source_label(
                    selection.source_kind
                ),
                "assessment_source_reason": selection.source_reason,
                "assessment_cutoff_outcome": cutoff_outcome,
                "assessment_cutoff_outcome_label": _assessment_outcome_label(
                    cutoff_outcome
                ),
                "assessment_final_outcome": final_outcome,
                "assessment_final_outcome_label": _assessment_outcome_label(
                    final_outcome
                ),
                "notes": response.result_note if response is not None else "",
            }
        )
        rows.append(row)
    return rows, totals


def _summary_rows(
    week_start: date,
    week_end: date,
    routine_totals: dict[str, int | float],
    review_rows: list[dict[str, str]],
    practice_rows: list[dict[str, str]],
    assessment_totals: dict[str, int | str],
) -> list[dict[str, str]]:
    practice_counts = {
        status: sum(row["practice_status"] == status for row in practice_rows)
        for status, _label in PracticeRun.Status.choices
    }
    review_counts = {
        rating: sum(row["review_rating"] == rating for row in review_rows)
        for rating, _label in ReviewRating.choices
    }
    metrics: list[tuple[str, str, int | float | str]] = [
        ("planned_minutes", "Planned minutes", routine_totals["planned_minutes"]),
        (
            "completed_seconds",
            "Completed seconds",
            routine_totals["completed_seconds"],
        ),
        (
            "completed_minutes",
            "Completed minutes",
            routine_totals["completed_minutes"],
        ),
        ("block_count", "Routine block count", routine_totals["block_count"]),
        (
            "completed_block_count",
            "Completed routine block count",
            routine_totals["completed_block_count"],
        ),
        (
            "pending_block_count",
            "Pending routine block count",
            routine_totals["pending_block_count"],
        ),
        (
            "carried_forward_count",
            "Carried-forward block count",
            routine_totals["carried_forward_count"],
        ),
        ("review_count", "Completed review count", len(review_rows)),
        ("practice_run_count", "Practice run count", len(practice_rows)),
        (
            "practice_passed_count",
            "Passed practice run count",
            practice_counts[PracticeRun.Status.PASSED],
        ),
        (
            "practice_failed_count",
            "Non-passing practice run count",
            len(practice_rows) - practice_counts[PracticeRun.Status.PASSED],
        ),
    ]
    metrics.extend(
        (
            f"review_{rating}_count",
            f"Review count: {label}",
            review_counts[rating],
        )
        for rating, label in ReviewRating.choices
    )
    metrics.extend(
        (f"practice_{status}_count", f"Practice run count: {label}", count)
        for (status, label), count in zip(PracticeRun.Status.choices, practice_counts.values())
    )
    metrics.extend(
        (
            metric,
            metric.replace("_", " ").capitalize(),
            value,
        )
        for metric, value in assessment_totals.items()
    )

    rows = []
    for metric, label, value in metrics:
        row = _empty_row("summary_total", week_start, week_end)
        row.update(
            {
                "summary_metric": metric,
                "summary_metric_label": label,
                "summary_value": _csv_value(value),
            }
        )
        rows.append(row)
    return rows


def export_weekly_csv(selected_date: date | datetime | None = None) -> str:
    """Return a rectangular CSV export for the week containing ``selected_date``.

    ``selected_date`` may be any date in the target Monday-through-Sunday
    week.  The default is the current local date.  Datetimes are converted to
    the application's local calendar date before the week is selected.
    """

    week_start = _selected_week_start(selected_date)
    week_end, start_at, end_at = _week_bounds(week_start)
    routine_rows, routine_totals = _routine_rows(week_start, week_end)
    review_rows = _review_rows(week_start, week_end, start_at, end_at)
    practice_rows = _practice_rows(week_start, week_end, start_at, end_at)
    assessment_rows, assessment_totals = _assessment_rows(week_start, week_end)
    summary_rows = _summary_rows(
        week_start,
        week_end,
        routine_totals,
        review_rows,
        practice_rows,
        assessment_totals,
    )

    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=CSV_HEADERS,
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    for row in (
        *routine_rows,
        *review_rows,
        *practice_rows,
        *assessment_rows,
        *summary_rows,
    ):
        writer.writerow({header: _csv_value(row.get(header)) for header in CSV_HEADERS})
    return output.getvalue()


# A descriptive alias for callers that prefer the construction verb.
build_weekly_csv = export_weekly_csv
