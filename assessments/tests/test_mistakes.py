from datetime import date, datetime, timedelta, timezone as dt_timezone

import pytest
from django.test import override_settings
from django.urls import reverse

from assessments.models import AssessmentMistake, AssessmentResponse, AssessmentSession
from assessments.services import (
    generate_assessment_mistakes,
    save_assessment_mistake,
    save_assessment_response,
    start_saturday_assessment,
    submit_assessment,
)
from curriculum.models import Concept, Topic
from planner.models import StudyBlock
from problems.models import Problem


WEEK_START = date(2026, 8, 31)
STARTED_AT = datetime(2026, 9, 5, 9, 0, tzinfo=dt_timezone.utc)


def _make_assessment():
    topic = Topic.objects.create(
        name="Arrays",
        slug="mistake-arrays",
        description="Mistake review fixtures.",
    )
    concept = Concept.objects.create(
        topic=topic,
        name="Traversal",
        slug="mistake-traversal",
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
    problems = [
        Problem.objects.create(
            concept=concept,
            title="Mistake Easy",
            slug="mistake-easy",
            statement="An easy mistake fixture.",
            difficulty=Problem.Difficulty.EASY,
            source_name="Fixture",
        ),
        Problem.objects.create(
            concept=concept,
            title="Mistake Medium One",
            slug="mistake-medium-one",
            statement="A first medium mistake fixture.",
            difficulty=Problem.Difficulty.MEDIUM,
            source_name="Fixture",
        ),
        Problem.objects.create(
            concept=concept,
            title="Mistake Medium Two",
            slug="mistake-medium-two",
            statement="A second medium mistake fixture.",
            difficulty=Problem.Difficulty.MEDIUM,
            source_name="Fixture",
        ),
    ]
    session = start_saturday_assessment(WEEK_START, STARTED_AT)
    return session, problems


def _complete_with_mistakes():
    session, problems = _make_assessment()
    outcomes = (
        AssessmentResponse.Outcome.SOLVED,
        AssessmentResponse.Outcome.NEEDS_REVIEW,
        AssessmentResponse.Outcome.SKIPPED,
    )
    for position, outcome in enumerate(outcomes, start=1):
        save_assessment_response(
            session,
            position,
            outcome=outcome,
            now=STARTED_AT + timedelta(minutes=position),
        )
    return submit_assessment(session, STARTED_AT + timedelta(minutes=10)), problems


@pytest.mark.django_db
def test_submission_generates_one_mistake_per_failed_or_skipped_problem():
    session, problems = _complete_with_mistakes()

    mistakes = list(
        AssessmentMistake.objects.filter(assessment=session).select_related(
            "problem", "response"
        )
    )

    assert session.status == AssessmentSession.Status.COMPLETED
    assert [mistake.problem_id for mistake in mistakes] == [problems[1].pk, problems[2].pk]
    assert all(mistake.assessment_id == session.pk for mistake in mistakes)
    assert [mistake.response.outcome for mistake in mistakes] == [
        AssessmentResponse.Outcome.NEEDS_REVIEW,
        AssessmentResponse.Outcome.SKIPPED,
    ]

    generate_assessment_mistakes(session)
    assert AssessmentMistake.objects.filter(assessment=session).count() == 2


@pytest.mark.django_db
def test_save_assessment_mistake_records_editable_diagnosis():
    session, _problems = _complete_with_mistakes()
    mistake = AssessmentMistake.objects.filter(assessment=session).first()

    save_assessment_mistake(
        mistake,
        cause=AssessmentMistake.Cause.EDGE_CASE_MISS,
        corrected_approach="Track the invariant before writing the loop.",
        next_action="Re-solve this Problem on Tuesday.",
    )
    mistake.refresh_from_db()

    assert mistake.assessment_id == session.pk
    assert mistake.problem_id == mistake.response.selection.problem_id
    assert mistake.cause == AssessmentMistake.Cause.EDGE_CASE_MISS
    assert mistake.corrected_approach.startswith("Track the invariant")
    assert mistake.next_action == "Re-solve this Problem on Tuesday."
    assert mistake.is_complete is False


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="assessments.tests.urls")
def test_mistake_page_lists_items_and_toggles_complete_incomplete(client):
    session, _problems = _complete_with_mistakes()
    url = reverse(
        "assessments:assessment_mistakes",
        kwargs={"session_id": session.pk},
    )

    page = client.get(url)
    body = page.content.decode()
    assert page.status_code == 200
    assert 'data-testid="assessment-mistakes"' in body
    assert body.count('data-testid="assessment-mistake"') == 2
    assert "Mistake Easy" not in body
    assert 'data-testid="mistake-status">Incomplete<' in body

    mistake = AssessmentMistake.objects.filter(assessment=session).first()
    saved = client.post(
        url,
        {
            "mistake": mistake.pk,
            "action": "complete",
            "cause": AssessmentMistake.Cause.CONCEPT_GAP,
            "corrected_approach": "Explain the invariant in plain language.",
            "next_action": "Re-solve tomorrow.",
        },
    )
    assert saved.status_code == 302
    mistake.refresh_from_db()
    assert mistake.is_complete is True
    assert saved.url.endswith("?saved=1")

    client.post(
        url,
        {
            "mistake": mistake.pk,
            "action": "incomplete",
            "cause": mistake.cause,
            "corrected_approach": mistake.corrected_approach,
            "next_action": mistake.next_action,
        },
    )
    mistake.refresh_from_db()
    assert mistake.is_complete is False
