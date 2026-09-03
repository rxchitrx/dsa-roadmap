from datetime import date, datetime, timedelta, timezone as dt_timezone

import pytest
from django.test import override_settings
from django.urls import reverse

from assessments.models import AssessmentResponse, AssessmentSession
from assessments.services import (
    generate_saturday_assessment_pool,
    navigate_assessment,
    refresh_assessment_session,
    save_assessment_response,
    start_saturday_assessment,
    submit_assessment,
)
from curriculum.models import Concept, Topic
from planner.models import StudyBlock
from problems.models import Problem


WEEK_START = date(2026, 8, 31)
STARTED_AT = datetime(2026, 9, 5, 9, 0, tzinfo=dt_timezone.utc)


def make_assessment_fixture():
    topic = Topic.objects.create(
        name="Arrays",
        slug="session-arrays",
        description="Assessment session fixtures.",
    )
    concept = Concept.objects.create(
        topic=topic,
        name="Traversal",
        slug="session-traversal",
        order=1,
        summary="Scan with an invariant.",
        intuition="Move through the sequence once.",
        explanation="Keep the useful state as you scan.",
        complexity_notes="O(n).",
        implementation_guidance="Name the invariant.",
        common_traps="Watch empty input.",
        guided_practice="Trace a short list.",
        checkpoint="What is true after each item?",
    )
    StudyBlock.objects.create(
        date=WEEK_START,
        week_start=WEEK_START,
        routine_key="0-concept",
        title="Learn one concept",
        planned_minutes=30,
        assigned_concept=concept,
        status=StudyBlock.Status.COMPLETED,
    )
    return [
        Problem.objects.create(
            concept=concept,
            title="Session Easy",
            slug="session-easy",
            statement="An easy assessment statement.",
            difficulty=Problem.Difficulty.EASY,
            source_name="Fixture",
        ),
        Problem.objects.create(
            concept=concept,
            title="Session Medium One",
            slug="session-medium-one",
            statement="A first medium assessment statement.",
            difficulty=Problem.Difficulty.MEDIUM,
            source_name="Fixture",
        ),
        Problem.objects.create(
            concept=concept,
            title="Session Medium Two",
            slug="session-medium-two",
            statement="A second medium assessment statement.",
            difficulty=Problem.Difficulty.MEDIUM,
            source_name="Fixture",
        ),
    ]


@pytest.fixture
def assessment_session_fixture(db):
    make_assessment_fixture()
    pool = generate_saturday_assessment_pool(WEEK_START)
    return start_saturday_assessment(WEEK_START, STARTED_AT), pool


@pytest.mark.django_db
def test_session_starts_once_with_ninety_minute_cutoff_and_resumes(
    assessment_session_fixture,
):
    session, pool = assessment_session_fixture

    assert session.pool_id == pool.pk
    assert session.duration_minutes == 90
    assert session.started_at == STARTED_AT
    assert session.cutoff_at == STARTED_AT + timedelta(minutes=90)
    assert session.status == AssessmentSession.Status.IN_PROGRESS
    assert session.responses.count() == 3

    first = session.responses.get(selection__position=1)
    save_assessment_response(
        session,
        1,
        draft_answer="def solve(nums):\n    return nums[0]",
        outcome=AssessmentResponse.Outcome.IN_PROGRESS,
        result_note="Need to check empty input.",
        now=STARTED_AT + timedelta(minutes=5),
    )
    resumed = start_saturday_assessment(
        WEEK_START,
        STARTED_AT + timedelta(minutes=10),
    )

    assert resumed.pk == session.pk
    assert resumed.responses.count() == 3
    first.refresh_from_db()
    assert first.draft_answer.startswith("def solve")
    assert first.outcome == AssessmentResponse.Outcome.IN_PROGRESS
    assert resumed.current_position == 1


@pytest.mark.django_db
def test_navigation_saves_draft_and_outcome_without_losing_previous_response(
    assessment_session_fixture,
):
    session, _pool = assessment_session_fixture
    save_assessment_response(
        session,
        1,
        draft_answer="draft for easy",
        outcome=AssessmentResponse.Outcome.SOLVED,
        now=STARTED_AT + timedelta(minutes=4),
    )
    navigate_assessment(session, 2, STARTED_AT + timedelta(minutes=4))
    save_assessment_response(
        session,
        2,
        draft_answer="draft for medium",
        outcome=AssessmentResponse.Outcome.NEEDS_REVIEW,
        now=STARTED_AT + timedelta(minutes=8),
    )
    navigate_assessment(session, 1, STARTED_AT + timedelta(minutes=8))

    session.refresh_from_db()
    assert session.current_position == 1
    assert session.responses.get(selection__position=1).draft_answer == "draft for easy"
    assert session.responses.get(selection__position=1).outcome == AssessmentResponse.Outcome.SOLVED
    assert session.responses.get(selection__position=2).draft_answer == "draft for medium"
    assert session.responses.get(selection__position=2).outcome == AssessmentResponse.Outcome.NEEDS_REVIEW


@pytest.mark.django_db
def test_cutoff_snapshot_is_preserved_while_overtime_responses_continue(
    assessment_session_fixture,
):
    session, _pool = assessment_session_fixture
    before_cutoff = STARTED_AT + timedelta(minutes=89)
    cutoff = STARTED_AT + timedelta(minutes=90)
    save_assessment_response(
        session,
        1,
        draft_answer="timed easy",
        outcome=AssessmentResponse.Outcome.SOLVED,
        now=before_cutoff,
    )
    refresh_assessment_session(session, cutoff)

    session.refresh_from_db()
    assert session.status == AssessmentSession.Status.OVERTIME
    assert session.cutoff_recorded_at == cutoff
    assert session.cutoff_snapshot["responses"][0]["outcome"] == "solved"

    save_assessment_response(
        session,
        2,
        draft_answer="overtime medium",
        outcome=AssessmentResponse.Outcome.SOLVED,
        now=cutoff + timedelta(minutes=12),
    )
    completed = submit_assessment(session, cutoff + timedelta(minutes=15))

    assert completed.status == AssessmentSession.Status.COMPLETED
    assert completed.final_summary["submitted_after_cutoff"] is True
    assert completed.final_summary["timed"]["easy"]["solved"] == 1
    assert completed.final_summary["timed"]["medium"]["solved"] == 0
    assert completed.final_summary["final"]["easy"]["solved"] == 1
    assert completed.final_summary["final"]["medium"]["solved"] == 1
    assert completed.final_summary["overtime_minutes"] == 15


@pytest.mark.django_db
def test_submit_inside_window_records_completed_timed_result(assessment_session_fixture):
    session, _pool = assessment_session_fixture
    save_assessment_response(
        session,
        1,
        outcome=AssessmentResponse.Outcome.SOLVED,
        now=STARTED_AT + timedelta(minutes=25),
    )
    completed = submit_assessment(session, STARTED_AT + timedelta(minutes=26))

    assert completed.status == AssessmentSession.Status.COMPLETED
    assert completed.cutoff_snapshot["responses"][0]["outcome"] == "solved"
    assert completed.final_summary["submitted_after_cutoff"] is False
    assert completed.final_summary["timed"] == completed.final_summary["final"]


@pytest.mark.django_db
def test_fallback_responses_have_a_separate_score_summary(db):
    current_week_problems = make_assessment_fixture()
    Problem.objects.filter(pk__in=[problem.pk for problem in current_week_problems]).delete()

    older_topic = Topic.objects.create(
        name="Stacks",
        slug="fallback-stacks",
        description="Older fallback assessment fixtures.",
    )
    older_concept = Concept.objects.create(
        topic=older_topic,
        name="Stack Basics",
        slug="fallback-stack-basics",
        order=1,
        summary="Use last-in-first-out state.",
        intuition="The newest item is the first one removed.",
        explanation="A stack exposes push and pop at one end.",
        complexity_notes="Push and pop are O(1).",
        implementation_guidance="Name the top of the stack.",
        common_traps="Popping an empty stack.",
        guided_practice="Trace three pushes and two pops.",
        checkpoint="Which item is visible at the top after every operation?",
    )
    StudyBlock.objects.create(
        date=WEEK_START - timedelta(days=7),
        week_start=WEEK_START - timedelta(days=7),
        routine_key="0-concept",
        title="Learn one older concept",
        planned_minutes=30,
        assigned_concept=older_concept,
        status=StudyBlock.Status.COMPLETED,
    )
    Problem.objects.create(
        concept=older_concept,
        title="Fallback Easy",
        slug="fallback-easy",
        statement="An older easy assessment problem.",
        difficulty=Problem.Difficulty.EASY,
        source_name="Fixture",
    )
    Problem.objects.create(
        concept=older_concept,
        title="Fallback Medium One",
        slug="fallback-medium-one",
        statement="An older medium assessment problem.",
        difficulty=Problem.Difficulty.MEDIUM,
        source_name="Fixture",
    )
    Problem.objects.create(
        concept=older_concept,
        title="Fallback Medium Two",
        slug="fallback-medium-two",
        statement="Another older medium assessment problem.",
        difficulty=Problem.Difficulty.MEDIUM,
        source_name="Fixture",
    )

    session = start_saturday_assessment(WEEK_START, STARTED_AT)
    for position, outcome in (
        (1, AssessmentResponse.Outcome.SOLVED),
        (2, AssessmentResponse.Outcome.SOLVED),
        (3, AssessmentResponse.Outcome.NEEDS_REVIEW),
    ):
        save_assessment_response(
            session,
            position,
            outcome=outcome,
            now=STARTED_AT + timedelta(minutes=position),
        )

    completed = submit_assessment(session, STARTED_AT + timedelta(minutes=10))

    assert completed.final_summary["final"]["easy"]["total"] == 0
    assert completed.final_summary["final"]["medium"]["total"] == 0
    assert completed.final_summary["final"]["fallback"]["total"] == 3
    assert completed.final_summary["final"]["fallback"]["easy"]["solved"] == 1
    assert completed.final_summary["final"]["fallback"]["medium"]["solved"] == 1
    assert completed.final_summary["final"]["fallback"]["medium"]["needs_review"] == 1


@pytest.mark.django_db
def test_invalid_navigation_position_is_rejected(assessment_session_fixture):
    session, _pool = assessment_session_fixture

    with pytest.raises(ValueError, match="does not exist"):
        navigate_assessment(session, 4, STARTED_AT)


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="assessments.tests.urls")
def test_start_route_redirects_to_session_and_session_ui_is_resumable(
    client,
    assessment_session_fixture,
):
    _session, _pool = assessment_session_fixture
    # The fixture already started it, so the start action exercises resume.
    response = client.post(
        reverse("assessments:start_assessment"),
        {"week": WEEK_START.isoformat()},
    )

    assert response.status_code == 302
    session = AssessmentSession.objects.get()
    assert response.url == reverse(
        "assessments:assessment_session",
        kwargs={"session_id": session.pk},
    )
    page = client.get(response.url)
    body = page.content.decode()
    assert page.status_code == 200
    assert 'data-testid="assessment-session"' in body
    assert 'data-testid="assessment-timer"' in body
    assert 'data-testid="assessment-response-form"' in body
    assert "Session Easy" in body


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="assessments.tests.urls")
def test_session_post_navigation_and_submission_render_final_easy_medium_summary(
    client,
    db,
):
    make_assessment_fixture()
    session = start_saturday_assessment(WEEK_START, STARTED_AT)
    session_url = reverse(
        "assessments:assessment_session",
        kwargs={"session_id": session.pk},
    )

    next_response = client.post(
        session_url,
        {
            "action": "next",
            "target_position": "2",
            "draft_answer": "easy solution",
            "outcome": AssessmentResponse.Outcome.SOLVED,
            "result_note": "Clean pass.",
        },
    )
    assert next_response.status_code == 302
    session.refresh_from_db()
    assert session.current_position == 2
    assert session.responses.get(selection__position=1).draft_answer == "easy solution"

    client.post(
        session_url,
        {
            "action": "next",
            "target_position": "3",
            "draft_answer": "medium one solution",
            "outcome": AssessmentResponse.Outcome.NEEDS_REVIEW,
        },
    )
    client.post(
        session_url,
        {
            "action": "submit",
            "draft_answer": "medium two solution",
            "outcome": AssessmentResponse.Outcome.SOLVED,
        },
    )

    completed = AssessmentSession.objects.get(pk=session.pk)
    page = client.get(session_url)
    body = page.content.decode()
    assert completed.status == AssessmentSession.Status.COMPLETED
    assert page.status_code == 200
    assert 'data-testid="assessment-complete"' in body
    assert 'data-testid="outcome-summary"' in body
    assert "TIMED CUTOFF" in body
    assert "FINAL" in body
    assert "Easy" in body
    assert "Medium" in body
