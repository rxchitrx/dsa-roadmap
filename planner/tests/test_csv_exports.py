import csv
import io
from datetime import date, datetime, timezone as dt_timezone

import pytest

from assessments.models import (
    AssessmentPool,
    AssessmentResponse,
    AssessmentSelection,
    AssessmentSession,
)
from planner.exports import CSV_HEADERS, export_weekly_csv
from planner.models import StudyBlock, WorkSession
from practice.models import PracticeRun
from problems.models import Problem
from reviews.models import ProblemReview, ProblemReviewEvent, ReviewRating


WEEK_START = date(2026, 8, 31)
UTC = dt_timezone.utc


def csv_rows(selected_date):
    content = export_weekly_csv(selected_date)
    return content, list(csv.DictReader(io.StringIO(content)))


@pytest.mark.django_db
def test_export_normalizes_selected_date_and_escapes_all_evidence_sections():
    block = StudyBlock.objects.create(
        date=date(2026, 9, 2),
        week_start=WEEK_START,
        routine_key="2-project",
        title='Build, "ship"\nnotes',
        planned_minutes=50,
        status=StudyBlock.Status.COMPLETED,
    )
    WorkSession.objects.create(
        study_block=block,
        status=WorkSession.Status.STOPPED,
        started_at=datetime(2026, 9, 2, 9, tzinfo=UTC),
        last_resumed_at=datetime(2026, 9, 2, 9, tzinfo=UTC),
        stopped_at=datetime(2026, 9, 2, 9, 25, 30, tzinfo=UTC),
        elapsed_seconds=1530,
    )
    problem = Problem.objects.create(
        title='Two, "quotes"\nProblem',
        slug="csv-escaping-problem",
        statement="Export fixture.",
        source_name="Fixture",
    )
    review = ProblemReview.objects.create(
        problem=problem,
        rating=ReviewRating.SOLVED_WITH_HELP,
        interval_days=3,
        due_at=datetime(2026, 9, 5, 12, tzinfo=UTC),
        last_reviewed_at=datetime(2026, 9, 2, 12, tzinfo=UTC),
    )
    ProblemReviewEvent.objects.create(
        review=review,
        rating=ReviewRating.SOLVED_WITH_HELP,
        interval_days=3,
        reviewed_at=datetime(2026, 9, 2, 12, tzinfo=UTC),
        due_at=datetime(2026, 9, 5, 12, tzinfo=UTC),
        note='Needs, "another" pass\nnext week',
    )
    practice = PracticeRun.objects.create(
        problem=problem,
        code="return 1",
        status=PracticeRun.Status.PASSED,
        passed_tests=2,
        total_tests=2,
        duration_ms=125,
        message='Passed, "cleanly"\nwith notes',
    )
    practice.created_at = datetime(2026, 9, 3, 13, tzinfo=UTC)
    practice.save(update_fields=("created_at",))

    pool = AssessmentPool.objects.create(
        week_start=WEEK_START,
        requested_problem_count=1,
        duration_minutes=90,
    )
    selection = AssessmentSelection.objects.create(
        pool=pool,
        problem=problem,
        position=1,
        slot_kind=AssessmentSelection.SlotKind.EASY,
        rationale="Fixture selection.",
    )
    session = AssessmentSession.objects.create(
        pool=pool,
        duration_minutes=90,
        started_at=datetime(2026, 9, 5, 9, tzinfo=UTC),
        cutoff_at=datetime(2026, 9, 5, 10, 30, tzinfo=UTC),
        status=AssessmentSession.Status.COMPLETED,
    )
    AssessmentResponse.objects.create(
        session=session,
        selection=selection,
        outcome=AssessmentResponse.Outcome.SOLVED,
        result_note='Solved, "independently"\nwithin time',
    )
    session.cutoff_snapshot = {
        "responses": [
            {
                "selection_id": selection.pk,
                "difficulty": "easy",
                "outcome": AssessmentResponse.Outcome.NEEDS_REVIEW,
            }
        ]
    }
    session.save(update_fields=("cutoff_snapshot",))

    content, rows = csv_rows(date(2026, 9, 4))

    assert content.startswith(",".join(CSV_HEADERS) + "\n")
    assert {row["record_type"] for row in rows} == {
        "routine_block",
        "review",
        "practice_run",
        "assessment_response",
        "summary_total",
    }
    assert all(len(row) == len(CSV_HEADERS) for row in rows)
    routine = next(row for row in rows if row["record_type"] == "routine_block")
    assert routine["week_start"] == "2026-08-31"
    assert routine["week_end"] == "2026-09-06"
    assert routine["date"] == "2026-09-02"
    assert routine["title"] == 'Build, "ship"\nnotes'
    assert routine["completed_seconds"] == "1530"
    assert routine["completed_minutes"] == "25.5"
    review_row = next(row for row in rows if row["record_type"] == "review")
    assert review_row["notes"] == 'Needs, "another" pass\nnext week'
    practice_row = next(row for row in rows if row["record_type"] == "practice_run")
    assert practice_row["practice_passed_tests"] == "2"
    assert practice_row["notes"] == 'Passed, "cleanly"\nwith notes'
    assessment_row = next(
        row for row in rows if row["record_type"] == "assessment_response"
    )
    assert assessment_row["assessment_cutoff_outcome"] == "needs_review"
    assert assessment_row["assessment_final_outcome"] == "solved"

    totals = {
        row["summary_metric"]: row["summary_value"]
        for row in rows
        if row["record_type"] == "summary_total"
    }
    assert totals["planned_minutes"] == "50"
    assert totals["completed_seconds"] == "1530"
    assert totals["completed_minutes"] == "25.5"
    assert totals["review_count"] == "1"
    assert totals["practice_passed_count"] == "1"
    assert totals["assessment_final_solved"] == "1"
    assert totals["assessment_final_total"] == "1"


@pytest.mark.django_db
def test_export_with_no_data_keeps_headers_and_zero_summary_totals():
    content, rows = csv_rows(WEEK_START)

    assert content.count("\n") == len(rows) + 1
    assert rows
    assert all(row["record_type"] == "summary_total" for row in rows)
    assert all(len(row) == len(CSV_HEADERS) for row in rows)
    totals = {
        row["summary_metric"]: row["summary_value"]
        for row in rows
    }
    assert totals["planned_minutes"] == "0"
    assert totals["completed_seconds"] == "0"
    assert totals["review_count"] == "0"
    assert totals["practice_run_count"] == "0"
    assert totals["assessment_present"] == "0"


@pytest.mark.django_db
def test_export_ignores_evidence_outside_selected_week():
    problem = Problem.objects.create(
        title="Outside range",
        slug="outside-range",
        statement="Export fixture.",
        source_name="Fixture",
    )
    run = PracticeRun.objects.create(
        problem=problem,
        code="return 1",
        status=PracticeRun.Status.PASSED,
    )
    run.created_at = datetime(2026, 9, 7, 0, tzinfo=UTC)
    run.save(update_fields=("created_at",))

    _content, rows = csv_rows(WEEK_START)

    assert not any(row["record_type"] == "practice_run" for row in rows)
    totals = {
        row["summary_metric"]: row["summary_value"]
        for row in rows
        if row["record_type"] == "summary_total"
    }
    assert totals["practice_run_count"] == "0"
