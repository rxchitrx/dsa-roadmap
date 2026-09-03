from datetime import date

import pytest
from django.test import override_settings
from django.urls import reverse

from assessments.services import generate_saturday_assessment_pool
from curriculum.models import Concept, Topic
from planner.models import StudyBlock
from problems.models import Problem


@pytest.fixture
def assessment_fixture(db):
    topic = Topic.objects.create(
        name="Arrays",
        slug="assessment-arrays",
        description="Assessment fixtures.",
    )
    concept = Concept.objects.create(
        topic=topic,
        name="Traversal",
        slug="assessment-traversal",
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
    week_start = date(2026, 8, 31)
    StudyBlock.objects.create(
        date=week_start,
        week_start=week_start,
        routine_key="0-concept",
        title="Learn one concept",
        planned_minutes=30,
        assigned_concept=concept,
        status=StudyBlock.Status.COMPLETED,
    )
    problems = [
        Problem.objects.create(
            concept=concept,
            title="View Easy",
            slug="view-easy",
            statement="An easy assessment statement.",
            difficulty=Problem.Difficulty.EASY,
            source_name="Fixture",
        ),
        Problem.objects.create(
            concept=concept,
            title="View Medium One",
            slug="view-medium-one",
            statement="A first medium assessment statement.",
            difficulty=Problem.Difficulty.MEDIUM,
            source_name="Fixture",
        ),
        Problem.objects.create(
            concept=concept,
            title="View Medium Two",
            slug="view-medium-two",
            statement="A second medium assessment statement.",
            difficulty=Problem.Difficulty.MEDIUM,
            source_name="Fixture",
        ),
    ]
    return week_start, problems


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="assessments.tests.urls")
def test_saturday_route_renders_selected_mix_and_rationale(client, assessment_fixture):
    week_start, problems = assessment_fixture

    response = client.get(
        reverse("assessments:saturday_pool"),
        {"week": week_start.isoformat()},
    )
    body = response.content.decode()

    assert response.status_code == 200
    assert 'data-testid="saturday-assessment"' in body
    assert 'data-testid="assessment-selection"' in body
    assert body.count('data-testid="assessment-selection"') == 3
    assert "1 easy · 2 medium" in body
    assert "Eligible Concepts studied this week" in body
    assert "Traversal" in body
    assert all(problem.title in body for problem in problems)


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="assessments.tests.urls")
def test_saturday_route_shows_sparse_state(client, assessment_fixture):
    week_start, problems = assessment_fixture
    Problem.objects.filter(pk__in=[problems[1].pk, problems[2].pk]).delete()

    response = client.get(
        reverse("assessments:saturday_pool"),
        {"week": week_start.isoformat()},
    )
    body = response.content.decode()

    assert response.status_code == 200
    assert 'data-testid="sparse-pool"' in body
    assert 'data-testid="assessment-selection"' in body
    assert body.count('data-testid="assessment-selection"') == 1
    assert "current-week pool is sparse" in body


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="assessments.tests.urls")
def test_saturday_route_rejects_invalid_week(client):
    response = client.get(
        reverse("assessments:saturday_pool"),
        {"week": "not-a-date"},
    )

    assert response.status_code == 400
    assert "YYYY-MM-DD" in response.content.decode()
