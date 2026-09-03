import pytest
from django.urls import reverse
from django.utils import timezone

from curriculum.models import Concept, Topic
from planner.models import StudyBlock
from planner.services import (
    assign_recommended_concept,
    generate_weekly_routine,
    week_start_for,
)


def make_concept(*, name="Arrays"):
    topic = Topic.objects.create(
        name=f"{name} topic",
        slug=f"{name.lower()}-topic",
        description="A DSA topic for planner assignment tests.",
        display_order=1,
    )
    return Concept.objects.create(
        topic=topic,
        name=name,
        slug=name.lower().replace(" ", "-"),
        order=1,
        summary="A focused concept.",
        intuition="Build the right mental model.",
        explanation="Use the concept deliberately.",
        examples=[],
        complexity_notes="Keep the complexity visible.",
        implementation_guidance="Implement the invariant.",
        common_traps="Do not skip the edge cases.",
        guided_practice="Trace one example.",
        checkpoint="Explain the idea from memory.",
    )


@pytest.fixture
def current_week_start():
    return week_start_for(timezone.localdate())


@pytest.mark.django_db
def test_assigns_recommendation_to_the_next_open_concept_block(current_week_start):
    concept = make_concept()
    generate_weekly_routine(current_week_start)

    assigned = assign_recommended_concept(current_week_start)

    assert assigned is not None
    assert assigned.assigned_concept_id == concept.pk
    assert assigned.concept_assignment_source == StudyBlock.ConceptAssignmentSource.AUTOMATIC
    assert assigned.routine_key.endswith("-concept")
    assert assigned.date == current_week_start


@pytest.mark.django_db
def test_repeating_assignment_returns_the_existing_assignment_without_duplication(
    current_week_start,
):
    make_concept()
    generate_weekly_routine(current_week_start)

    first = assign_recommended_concept(current_week_start)
    second = assign_recommended_concept(current_week_start)

    assert second.pk == first.pk
    assert StudyBlock.objects.filter(
        week_start=current_week_start,
        assigned_concept__isnull=False,
    ).count() == 1


@pytest.mark.django_db
def test_manual_concept_is_preserved_and_recommendation_uses_the_next_block(
    current_week_start,
):
    manual_concept = make_concept(name="Manual choice")
    recommended_concept = make_concept(name="Recommended choice")
    generate_weekly_routine(current_week_start)

    first_concept_block = StudyBlock.objects.get(
        week_start=current_week_start,
        routine_key="0-concept",
    )
    first_concept_block.assigned_concept = manual_concept
    first_concept_block.concept_assignment_source = (
        StudyBlock.ConceptAssignmentSource.MANUAL
    )
    first_concept_block.save(
        update_fields=(
            "assigned_concept",
            "concept_assignment_source",
            "updated_at",
        )
    )

    # Make the manual choice ineligible for recommendation, leaving the other
    # Concept as the next eligible recommendation.
    from progress.models import ConceptCheckpoint

    ConceptCheckpoint.objects.create(
        concept=manual_concept,
        confidence=ConceptCheckpoint.Confidence.CONFIDENT,
        recall_response="I can explain this one.",
    )

    assigned = assign_recommended_concept(current_week_start)

    first_concept_block.refresh_from_db()
    assert first_concept_block.assigned_concept_id == manual_concept.pk
    assert first_concept_block.concept_assignment_source == StudyBlock.ConceptAssignmentSource.MANUAL
    assert assigned.assigned_concept_id == recommended_concept.pk
    assert assigned.routine_key == "1-concept"


@pytest.mark.django_db
def test_today_auto_assignment_links_to_the_concept_lesson(client, current_week_start):
    concept = make_concept()
    generate_weekly_routine(current_week_start)

    response = client.get(reverse("planner:today"))

    assert response.status_code == 200
    assigned = StudyBlock.objects.get(
        week_start=current_week_start,
        assigned_concept=concept,
    )
    assert response.context["study_blocks"]
    assert assigned.date == timezone.localdate()
    html = response.content.decode()
    assert 'data-testid="assigned-concept"' in html
    assert reverse(
        "curriculum:concept_detail",
        kwargs={"concept_slug": concept.slug},
    ) in html


@pytest.mark.django_db
def test_weekly_plan_shows_the_auto_assignment_and_lesson_link(
    client,
    current_week_start,
):
    concept = make_concept()
    generate_weekly_routine(current_week_start)

    response = client.get(reverse("planner:weekly_plan"))

    assert response.status_code == 200
    html = response.content.decode()
    assert 'data-testid="assigned-concept"' in html
    assert "Recommended concept" in html
    assert reverse(
        "curriculum:concept_detail",
        kwargs={"concept_slug": concept.slug},
    ) in html


@pytest.mark.django_db
def test_weekly_plan_allows_a_learner_to_select_a_concept(client, current_week_start):
    first_concept = make_concept()
    second_concept = make_concept(name="Selected concept")
    generate_weekly_routine(current_week_start)
    block = StudyBlock.objects.get(
        week_start=current_week_start,
        routine_key="0-concept",
    )

    response = client.post(
        reverse("planner:edit_study_block", args=[block.pk]),
        {
            "title": block.title,
            "planned_minutes": block.planned_minutes,
            "assigned_concept": second_concept.pk,
        },
    )

    assert response.status_code == 302
    block.refresh_from_db()
    assert block.assigned_concept_id == second_concept.pk
    assert block.concept_assignment_source == StudyBlock.ConceptAssignmentSource.MANUAL
    assert first_concept.pk != block.assigned_concept_id
