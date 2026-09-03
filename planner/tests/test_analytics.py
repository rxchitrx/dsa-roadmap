from datetime import date, datetime, timedelta, timezone as dt_timezone

import pytest

from curriculum.models import Concept, Topic
from planner.analytics import get_progress_analytics, resolve_analytics_range
from planner.models import StudyBlock, WorkSession
from practice.models import (
    LearningStatus,
    LearningStatusEvent,
    PracticeRun,
    ProblemLearningStatus,
)
from problems.models import Problem
from problems.services import ensure_problem_snapshot
from progress.models import ConceptCheckpoint
from reviews.models import ProblemReview, ProblemReviewEvent, ReviewRating


START = date(2026, 8, 31)
END = date(2026, 9, 6)
UTC = dt_timezone.utc


def at(day: date, hour: int = 12, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=UTC)


def make_topic(slug="arrays"):
    return Topic.objects.create(
        name=slug.replace("-", " ").title(),
        slug=slug,
        description="Analytics fixture topic.",
        display_order=1,
    )


def make_concept(topic, *, slug, name, order):
    return Concept.objects.create(
        topic=topic,
        name=name,
        slug=slug,
        order=order,
        summary="Fixture summary.",
        intuition="Fixture intuition.",
        explanation="Fixture explanation.",
        examples=[],
        complexity_notes="O(n).",
        implementation_guidance="State the invariant.",
        common_traps="Check edge cases.",
        guided_practice="Trace a small example.",
        checkpoint="Explain it without notes.",
    )


def make_problem(slug, *, concept=None, active=True):
    return Problem.objects.create(
        concept=concept,
        title=slug.replace("-", " ").title(),
        slug=slug,
        statement="Analytics fixture problem.",
        difficulty=Problem.Difficulty.EASY,
        source_name="Fixture",
        is_active=active,
    )


def set_created_at(instance, value):
    instance.created_at = value
    instance.save(update_fields=("created_at",))


def set_submitted_at(checkpoint, value):
    checkpoint.submitted_at = value
    checkpoint.save(update_fields=("submitted_at",))


def set_changed_at(event, value):
    event.changed_at = value
    event.save(update_fields=("changed_at",))


def make_checkpoint(concept, confidence, day):
    checkpoint = ConceptCheckpoint.objects.create(
        concept=concept,
        confidence=confidence,
        recall_response="I can explain the invariant from memory.",
    )
    set_submitted_at(checkpoint, at(day))
    return checkpoint


def make_run(problem, status, day):
    run = PracticeRun.objects.create(
        problem=problem,
        code="def solve():\n    return True\n",
        status=status,
        passed_tests=2 if status == PracticeRun.Status.PASSED else 0,
        total_tests=2,
    )
    set_created_at(run, at(day, 13))
    return run


def make_status_event(problem, status, day, reason="Fixture status evidence."):
    learning_status = ProblemLearningStatus.objects.create(
        problem=problem,
        status=status,
        reason=reason,
    )
    event = LearningStatusEvent.objects.create(
        learning_status=learning_status,
        problem_snapshot=ensure_problem_snapshot(problem)[0],
        status=status,
        reason=reason,
    )
    set_changed_at(event, at(day, 14))
    return event


def make_review_event(problem, rating, day):
    review, _created = ProblemReview.objects.get_or_create(
        problem=problem,
        defaults={
            "rating": rating,
            "interval_days": 3,
            "due_at": at(day) + timedelta(days=3),
            "last_reviewed_at": at(day),
        },
    )
    return ProblemReviewEvent.objects.create(
        review=review,
        rating=rating,
        interval_days=3,
        reviewed_at=at(day, 15),
        due_at=review.due_at,
    )


@pytest.mark.django_db
def test_range_resolution_is_inclusive_and_supports_single_boundaries():
    assert resolve_analytics_range(today=END).start_date == date(2026, 8, 8)
    assert resolve_analytics_range(end_date=END).start_date == date(2026, 8, 8)
    assert resolve_analytics_range(start_date=START).end_date == date(2026, 9, 29)

    with pytest.raises(ValueError, match="on or before"):
        resolve_analytics_range(start_date=END, end_date=START)


@pytest.mark.django_db
def test_concept_coverage_uses_latest_checkpoint_inside_selected_range():
    topic = make_topic()
    covered = make_concept(topic, slug="covered", name="Covered", order=1)
    weak = make_concept(topic, slug="weak", name="Weak", order=2)
    missing = make_concept(topic, slug="missing", name="Missing", order=3)

    make_checkpoint(covered, ConceptCheckpoint.Confidence.DEVELOPING, START - timedelta(days=1))
    make_checkpoint(covered, ConceptCheckpoint.Confidence.CONFIDENT, START)
    make_checkpoint(weak, ConceptCheckpoint.Confidence.SOLID, START + timedelta(days=2))

    analytics = get_progress_analytics(START, END)
    concepts = analytics["concepts"]

    assert concepts["total_count"] == 3
    assert concepts["covered_count"] == 2
    assert concepts["uncovered_count"] == 1
    assert concepts["coverage_percent"] == 66.7
    assert concepts["checkpoint_count"] == 2
    assert concepts["status_counts"] == {
        "not_yet": 0,
        "developing": 0,
        "solid": 1,
        "confident": 1,
        "teachable": 0,
    }
    assert concepts["by_topic"][0]["coverage_percent"] == 66.7
    assert concepts["by_topic"][0]["status_counts"]["confident"] == 1
    by_name = {row["name"]: row for row in concepts["by_concept"]}
    assert by_name["Covered"]["confidence_label"] == "Confident"
    assert by_name["Missing"]["missing_data"]

    outside = get_progress_analytics(START - timedelta(days=2), START - timedelta(days=1))
    assert outside["concepts"]["covered_count"] == 1
    assert outside["concepts"]["status_counts"]["developing"] == 1


@pytest.mark.django_db
def test_problem_outcomes_separate_practice_attempts_passing_and_explicit_mastery():
    topic = make_topic()
    concept = make_concept(topic, slug="problem-concept", name="Problem Concept", order=1)
    attempted = make_problem("attempted", concept=concept)
    passing = make_problem("passing", concept=concept)
    helped = make_problem("helped", concept=concept)
    independent = make_problem("independent", concept=concept)

    make_run(attempted, PracticeRun.Status.RUNTIME_ERROR, START)
    make_run(passing, PracticeRun.Status.PASSED, START + timedelta(days=1))
    make_status_event(helped, LearningStatus.SOLVED_WITH_HELP, START + timedelta(days=2))
    make_status_event(independent, LearningStatus.SOLVED_INDEPENDENTLY, START + timedelta(days=3))
    make_run(independent, PracticeRun.Status.PASSED, START + timedelta(days=3))
    make_run(attempted, PracticeRun.Status.PASSED, START - timedelta(days=1))

    analytics = get_progress_analytics(START, END)["problems"]

    assert analytics["practice_run_count"] == 3
    assert analytics["run_status_counts"][PracticeRun.Status.PASSED] == 2
    assert analytics["outcomes"] == {
        "attempted": 3,
        "passing": 2,
        "solved_with_help": 1,
        "solved_independently": 1,
    }
    assert analytics["learning_status_counts"] == {
        LearningStatus.UNSEEN: 0,
        LearningStatus.ATTEMPTED: 0,
        LearningStatus.SOLVED_WITH_HELP: 1,
        LearningStatus.SOLVED_INDEPENDENTLY: 1,
    }


@pytest.mark.django_db
def test_review_retention_counts_ratings_rates_and_filters_by_reviewed_at():
    p1 = make_problem("review-one")
    p2 = make_problem("review-two")
    p3 = make_problem("review-three")
    make_review_event(p1, ReviewRating.SOLVED_INDEPENDENTLY, START)
    make_review_event(p2, ReviewRating.SOLVED_WITH_HELP, START + timedelta(days=1))
    make_review_event(p3, ReviewRating.COULD_NOT_SOLVE, START + timedelta(days=2))
    make_review_event(p1, ReviewRating.COULD_NOT_SOLVE, START - timedelta(days=1))

    reviews = get_progress_analytics(START, END)["reviews"]

    assert reviews["review_count"] == 3
    assert reviews["unique_problem_count"] == 3
    assert reviews["rating_counts"] == {
        ReviewRating.COULD_NOT_SOLVE: 1,
        ReviewRating.SOLVED_WITH_HELP: 1,
        ReviewRating.SOLVED_INDEPENDENTLY: 1,
    }
    assert reviews["independent_recall_count"] == 1
    assert reviews["successful_recall_count"] == 2
    assert reviews["independent_retention_percent"] == 33.3
    assert reviews["successful_recall_percent"] == 66.7
    assert sum(row["review_count"] for row in reviews["by_day"]) == 3


@pytest.mark.django_db
def test_completed_work_session_time_uses_stop_timestamp_and_explains_active_timers():
    block = StudyBlock.objects.create(
        date=START,
        week_start=START,
        title="Analytics block",
        planned_minutes=30,
    )
    WorkSession.objects.create(
        study_block=block,
        status=WorkSession.Status.STOPPED,
        started_at=at(START, 9),
        last_resumed_at=at(START, 9),
        stopped_at=at(START, 9, 20),
        elapsed_seconds=1200,
    )
    WorkSession.objects.create(
        study_block=block,
        status=WorkSession.Status.PAUSED,
        started_at=at(START + timedelta(days=1), 9),
        last_resumed_at=at(START + timedelta(days=1), 9),
        elapsed_seconds=600,
    )
    outside_block = StudyBlock.objects.create(
        date=START - timedelta(days=1),
        week_start=START - timedelta(days=7),
        title="Outside block",
        planned_minutes=30,
    )
    WorkSession.objects.create(
        study_block=outside_block,
        status=WorkSession.Status.STOPPED,
        started_at=at(START - timedelta(days=1), 23),
        last_resumed_at=at(START - timedelta(days=1), 23),
        stopped_at=at(START - timedelta(days=1), 23),
        elapsed_seconds=5000,
    )

    time_data = get_progress_analytics(START, END)["time"]

    assert time_data["completed_session_count"] == 1
    assert time_data["completed_seconds"] == 1200
    assert time_data["completed_minutes"] == 20
    assert time_data["by_day"][0]["minutes"] == 20
    assert time_data["active_session_count"] == 1
    assert any("running or paused" in message for message in time_data["missing_data"])


@pytest.mark.django_db
def test_consistency_unions_evidence_sources_and_calculates_streaks():
    topic = make_topic()
    concept = make_concept(topic, slug="consistency-concept", name="Consistency", order=1)
    problem = make_problem("consistency-problem", concept=concept)

    make_checkpoint(concept, ConceptCheckpoint.Confidence.SOLID, START)
    make_run(problem, PracticeRun.Status.PASSED, START + timedelta(days=1))
    make_review_event(problem, ReviewRating.SOLVED_INDEPENDENTLY, START + timedelta(days=2))
    make_status_event(problem, LearningStatus.SOLVED_INDEPENDENTLY, START + timedelta(days=3))
    make_review_event(problem, ReviewRating.SOLVED_WITH_HELP, START + timedelta(days=5))

    consistency = get_progress_analytics(START, END)["consistency"]

    assert consistency["active_day_count"] == 5
    assert consistency["consistency_percent"] == 71.4
    assert consistency["current_streak_days"] == 0
    assert consistency["longest_streak_days"] == 4
    assert consistency["active_dates"] == [
        START,
        START + timedelta(days=1),
        START + timedelta(days=2),
        START + timedelta(days=3),
        START + timedelta(days=5),
    ]

    narrowed = get_progress_analytics(START + timedelta(days=1), START + timedelta(days=3))
    assert narrowed["consistency"]["active_dates"] == [
        START + timedelta(days=1),
        START + timedelta(days=2),
        START + timedelta(days=3),
    ]
    assert narrowed["consistency"]["current_streak_days"] == 3


@pytest.mark.django_db
def test_empty_analytics_explains_each_unavailable_section():
    analytics = get_progress_analytics(START, END)

    assert analytics["has_data"] is False
    assert analytics["missing_data"]
    assert analytics["concepts"]["coverage_percent"] is None
    assert analytics["reviews"]["independent_retention_percent"] is None
    assert analytics["consistency"]["current_streak_days"] == 0
    assert analytics["time"]["completed_minutes"] == 0
