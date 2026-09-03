from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta

from django.db.models import Sum
from django.utils import timezone

from assessments.models import AssessmentMistake, AssessmentPool, AssessmentSession
from assessments.services import get_assessment_summary
from practice.models import PracticeRun
from reviews.models import ProblemReview, ProblemReviewEvent

from .models import StudyBlock, WorkSession
from .services import week_start_for


_BLOCK_TYPE_LABELS = {
    "review": "Reviews",
    "concept": "Concept learning",
    "problems": "Problem solving",
    "rewrite": "Solution rewrite",
    "project": "Project / Python",
    "cs-subject": "CS subject",
    "assessment": "Assessment",
    "mistake-analysis": "Mistake analysis",
    "review-batch": "Sunday review batch",
    "cs-revision": "CS revision",
    "planning": "Next-week planning",
}


def _week_datetimes(week_start: date) -> tuple[datetime, datetime]:
    current_timezone = timezone.get_current_timezone()
    start_at = timezone.make_aware(datetime.combine(week_start, time.min), current_timezone)
    end_at = start_at + timedelta(days=7)
    return start_at, end_at


def _minutes(seconds: int) -> int | float:
    minutes = round(seconds / 60, 1)
    return int(minutes) if minutes.is_integer() else minutes


def _block_type_label(block: StudyBlock) -> str:
    if block.is_carried_forward:
        return _block_type_label(block.carried_from)
    if block.routine_key:
        suffix = block.routine_key.split("-", 1)[-1]
        return _BLOCK_TYPE_LABELS.get(suffix, block.title)
    return block.title


def _empty_type_row(label: str = "") -> dict:
    return {
        "label": label,
        "planned_minutes": 0,
        "completed_minutes": 0,
        "block_count": 0,
        "completed_block_count": 0,
    }


def _assessment_data(session: AssessmentSession | None) -> dict | None:
    if session is None:
        return None

    summary = session.final_summary or get_assessment_summary(session)
    final = summary.get("final", {})
    fallback = final.get("fallback", {})
    current_week_solved = final.get("solved", 0)
    current_week_total = final.get("total", 0)
    fallback_solved = fallback.get("solved", 0)
    fallback_total = fallback.get("total", 0)
    total_solved = current_week_solved + fallback_solved
    total = current_week_total + fallback_total
    mistakes_remaining = AssessmentMistake.objects.filter(
        assessment=session,
        is_complete=False,
    ).count()
    return {
        "session_id": session.pk,
        "status": session.status,
        "status_label": session.get_status_display(),
        "is_complete": session.status == AssessmentSession.Status.COMPLETED,
        "solved": total_solved,
        "total": total,
        "score_label": f"{total_solved}/{total} solved" if total else "No score yet",
        "current_week_solved": current_week_solved,
        "current_week_total": current_week_total,
        "current_week_score_label": (
            f"{current_week_solved}/{current_week_total} solved"
            if current_week_total
            else "No current-week score"
        ),
        "fallback_solved": fallback_solved,
        "fallback_total": fallback_total,
        "fallback_score_label": (
            f"{fallback_solved}/{fallback_total} solved"
            if fallback_total
            else "No fallback score"
        ),
        "mistakes_remaining": mistakes_remaining,
    }


def get_weekly_summary(week_start: date | None = None) -> dict:
    """Aggregate one local calendar week into actionable learner evidence."""

    start = week_start_for(week_start or timezone.localdate())
    end = start + timedelta(days=6)
    start_at, end_at = _week_datetimes(start)

    blocks = list(
        StudyBlock.objects.filter(date__range=(start, end)).order_by(
            "date", "position", "id"
        )
    )
    block_ids = [block.pk for block in blocks]
    actual_seconds_by_block = {
        row["study_block_id"]: row["total"] or 0
        for row in WorkSession.objects.filter(
            study_block_id__in=block_ids,
            status=WorkSession.Status.STOPPED,
        )
        .values("study_block_id")
        .annotate(total=Sum("elapsed_seconds"))
    }

    daily_rows = {
        start + timedelta(days=offset): {
            "date": start + timedelta(days=offset),
            "label": (start + timedelta(days=offset)).strftime("%A"),
            "planned_minutes": 0,
            "completed_minutes": 0,
            "block_count": 0,
            "completed_block_count": 0,
        }
        for offset in range(7)
    }
    type_rows = defaultdict(_empty_type_row)
    for block in blocks:
        actual_minutes = _minutes(actual_seconds_by_block.get(block.pk, 0))
        day_row = daily_rows[block.date]
        day_row["planned_minutes"] += block.planned_minutes
        day_row["completed_minutes"] += actual_minutes
        day_row["block_count"] += 1
        day_row["completed_block_count"] += block.status == StudyBlock.Status.COMPLETED

        type_label = _block_type_label(block)
        type_row = type_rows[type_label]
        type_row["label"] = type_label
        type_row["planned_minutes"] += block.planned_minutes
        type_row["completed_minutes"] += actual_minutes
        type_row["block_count"] += 1
        type_row["completed_block_count"] += block.status == StudyBlock.Status.COMPLETED

    pending_blocks = [block for block in blocks if block.status != StudyBlock.Status.COMPLETED]
    carried_forward_count = sum(block.is_carried_forward for block in blocks)
    planned_minutes = sum(row["planned_minutes"] for row in daily_rows.values())
    completed_minutes = sum(row["completed_minutes"] for row in daily_rows.values())
    completed_block_count = sum(row["completed_block_count"] for row in daily_rows.values())

    review_events = ProblemReviewEvent.objects.filter(
        reviewed_at__gte=start_at,
        reviewed_at__lt=end_at,
    )
    review_counts = Counter(review_events.values_list("rating", flat=True))
    due_reviews_remaining = ProblemReview.objects.filter(
        due_at__lt=end_at,
        problem__is_active=True,
    ).count()

    practice_runs = PracticeRun.objects.filter(
        created_at__gte=start_at,
        created_at__lt=end_at,
    )
    practice_run_count = practice_runs.count()
    practice_passed_count = practice_runs.filter(status=PracticeRun.Status.PASSED).count()

    assessment = (
        AssessmentSession.objects.select_related("pool")
        .filter(pool__week_start=start)
        .first()
    )
    assessment_data = _assessment_data(assessment)

    next_actions = []
    if pending_blocks:
        next_actions.append(
            {
                "key": "unfinished_blocks",
                "title": f"Finish {len(pending_blocks)} unfinished block{'s' if len(pending_blocks) != 1 else ''}",
                "body": "Carry the incomplete work into your next active study session.",
            }
        )
    if due_reviews_remaining:
        next_actions.append(
            {
                "key": "due_reviews",
                "title": f"Clear {due_reviews_remaining} due review{'s' if due_reviews_remaining != 1 else ''}",
                "body": "Re-solve the oldest due Problems before adding more new work.",
            }
        )
    if assessment_data and assessment_data["mistakes_remaining"]:
        remaining = assessment_data["mistakes_remaining"]
        next_actions.append(
            {
                "key": "assessment_mistakes",
                "title": f"Complete {remaining} Assessment mistake review{'s' if remaining != 1 else ''}",
                "body": "Name the cause, corrected approach, and next action for every miss.",
                "session_id": assessment_data["session_id"],
            }
        )
    if not next_actions:
        next_actions.append(
            {
                "key": "keep_loop",
                "title": "Keep the loop going",
                "body": "Your selected week has no outstanding next action in the tracker.",
            }
        )

    return {
        "week_start": start,
        "week_end": end,
        "days": list(daily_rows.values()),
        "by_type": list(
            sorted(
                type_rows.values(),
                key=lambda row: (-row["planned_minutes"], row["label"]),
            )
        ),
        "totals": {
            "planned_minutes": planned_minutes,
            "completed_minutes": completed_minutes,
            "block_count": len(blocks),
            "completed_block_count": completed_block_count,
            "pending_block_count": len(pending_blocks),
            "carried_forward_count": carried_forward_count,
        },
        "reviews": {
            "completed_count": review_events.count(),
            "due_remaining": due_reviews_remaining,
            "counts": dict(review_counts),
        },
        "practice": {
            "run_count": practice_run_count,
            "passed_count": practice_passed_count,
            "failed_count": practice_run_count - practice_passed_count,
        },
        "assessment": assessment_data,
        "next_actions": next_actions,
    }
