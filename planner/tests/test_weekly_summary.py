from datetime import date, datetime, timedelta, timezone as dt_timezone

import pytest
from django.test import override_settings
from django.urls import reverse

from planner.models import StudyBlock, WorkSession
from planner.summary import get_weekly_summary


WEEK_START = date(2026, 8, 31)


@pytest.mark.django_db
def test_weekly_summary_aggregates_days_types_and_carry_forward_without_leaking_weeks():
    source = StudyBlock.objects.create(
        date=WEEK_START - timedelta(days=1),
        week_start=WEEK_START - timedelta(days=7),
        routine_key="6-project",
        title="Prior project",
        planned_minutes=120,
        status=StudyBlock.Status.PENDING,
    )
    monday = StudyBlock.objects.create(
        date=WEEK_START,
        week_start=WEEK_START,
        routine_key="0-review",
        title="Review",
        planned_minutes=20,
        status=StudyBlock.Status.COMPLETED,
    )
    WorkSession.objects.create(
        study_block=monday,
        status=WorkSession.Status.STOPPED,
        started_at=datetime(2026, 8, 31, 9, tzinfo=dt_timezone.utc),
        last_resumed_at=datetime(2026, 8, 31, 9, tzinfo=dt_timezone.utc),
        stopped_at=datetime(2026, 8, 31, 9, 20, tzinfo=dt_timezone.utc),
        elapsed_seconds=1200,
    )
    tuesday = StudyBlock.objects.create(
        date=WEEK_START + timedelta(days=1),
        week_start=WEEK_START,
        routine_key="1-concept",
        title="Concept",
        planned_minutes=30,
        status=StudyBlock.Status.PENDING,
        carried_from=source,
    )
    WorkSession.objects.create(
        study_block=tuesday,
        status=WorkSession.Status.STOPPED,
        started_at=datetime(2026, 9, 1, 9, tzinfo=dt_timezone.utc),
        last_resumed_at=datetime(2026, 9, 1, 9, tzinfo=dt_timezone.utc),
        stopped_at=datetime(2026, 9, 1, 9, 10, tzinfo=dt_timezone.utc),
        elapsed_seconds=600,
    )

    summary = get_weekly_summary(WEEK_START)

    assert summary["week_start"] == WEEK_START
    assert summary["totals"] == {
        "planned_minutes": 50,
        "completed_minutes": 30,
        "block_count": 2,
        "completed_block_count": 1,
        "pending_block_count": 1,
        "carried_forward_count": 1,
    }
    assert summary["days"][0]["completed_minutes"] == 20
    assert summary["days"][1]["completed_minutes"] == 10
    assert {row["label"] for row in summary["by_type"]} == {"Reviews", "Project / Python"}
    assert summary["next_actions"][0]["key"] == "unfinished_blocks"


@pytest.mark.django_db
def test_weekly_summary_counts_review_and_practice_evidence_in_local_week():
    from problems.models import Problem
    from reviews.models import ProblemReview, ProblemReviewEvent, ReviewRating

    problem = Problem.objects.create(
        title="Summary problem",
        slug="summary-problem",
        statement="A summary fixture.",
        source_name="Fixture",
    )
    review = ProblemReview.objects.create(
        problem=problem,
        rating=ReviewRating.SOLVED_WITH_HELP,
        interval_days=3,
        due_at=datetime(2026, 9, 2, tzinfo=dt_timezone.utc),
        last_reviewed_at=datetime(2026, 9, 1, tzinfo=dt_timezone.utc),
    )
    ProblemReviewEvent.objects.create(
        review=review,
        rating=ReviewRating.SOLVED_WITH_HELP,
        interval_days=3,
        reviewed_at=datetime(2026, 9, 1, 12, tzinfo=dt_timezone.utc),
        due_at=datetime(2026, 9, 4, 12, tzinfo=dt_timezone.utc),
    )
    from practice.models import PracticeRun

    passed = PracticeRun.objects.create(
        problem=problem,
        code="def solve(): pass",
        status=PracticeRun.Status.PASSED,
        passed_tests=1,
        total_tests=1,
    )
    failed = PracticeRun.objects.create(
        problem=problem,
        code="raise ValueError()",
        status=PracticeRun.Status.RUNTIME_ERROR,
    )
    passed.created_at = datetime(2026, 9, 1, 13, tzinfo=dt_timezone.utc)
    passed.save(update_fields=("created_at",))
    failed.created_at = datetime(2026, 9, 2, 13, tzinfo=dt_timezone.utc)
    failed.save(update_fields=("created_at",))

    summary = get_weekly_summary(WEEK_START)

    assert summary["reviews"]["completed_count"] == 1
    assert summary["reviews"]["counts"] == {ReviewRating.SOLVED_WITH_HELP: 1}
    assert summary["practice"] == {"run_count": 2, "passed_count": 1, "failed_count": 1}


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="dsa_roadmap.urls")
def test_weekly_summary_view_normalizes_week_selection_and_handles_empty_weeks(client):
    response = client.get(
        reverse("planner:weekly_summary"),
        {"week": "2026-09-02"},
    )
    body = response.content.decode()

    assert response.status_code == 200
    assert response.context["summary"]["week_start"] == WEEK_START
    assert 'data-testid="weekly-summary"' in body
    assert 'data-testid="summary-empty-types"' in body
    assert "No Assessment recorded" in body

    invalid = client.get(reverse("planner:weekly_summary"), {"week": "bad-date"})
    assert invalid.status_code == 400
