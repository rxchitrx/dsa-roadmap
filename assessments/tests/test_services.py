from datetime import date, timedelta

import pytest

from assessments.models import AssessmentSelection
from assessments.services import (
    generate_saturday_assessment_pool,
    get_studied_concept_evidence,
)
from curriculum.models import Concept, Topic
from planner.models import StudyBlock
from practice.models import LearningStatus, ProblemLearningStatus
from problems.models import Problem


def make_concept(topic_slug, concept_slug, *, order=1):
    topic = Topic.objects.create(
        name=topic_slug.replace("-", " ").title(),
        slug=topic_slug,
        description="Assessment fixture topic.",
    )
    return Concept.objects.create(
        topic=topic,
        name=concept_slug.replace("-", " ").title(),
        slug=concept_slug,
        order=order,
        summary="A test Concept.",
        intuition="Build a reliable intuition.",
        explanation="Use the invariant.",
        complexity_notes="O(n).",
        implementation_guidance="State the invariant first.",
        common_traps="Watch the edge cases.",
        guided_practice="Trace one example.",
        checkpoint="Explain the invariant.",
    )


def make_problem(concept, slug, difficulty, *, display_order=1):
    return Problem.objects.create(
        concept=concept,
        title=slug.replace("-", " ").title(),
        slug=slug,
        statement="Solve this assessment fixture.",
        difficulty=difficulty,
        source_name="Fixture",
        display_order=display_order,
    )


def mark_concept_studied(concept, week_start, *, status=StudyBlock.Status.COMPLETED):
    return StudyBlock.objects.create(
        date=week_start + timedelta(days=2),
        week_start=week_start,
        routine_key="2-concept",
        title="Learn one concept",
        planned_minutes=30,
        assigned_concept=concept,
        status=status,
    )


@pytest.fixture
def studied_concept(db):
    concept = make_concept("arrays", "array-traversal")
    mark_concept_studied(concept, date(2026, 8, 31))
    return concept


@pytest.mark.django_db
def test_selects_one_easy_and_two_medium_from_studied_concepts(studied_concept):
    week_start = date(2026, 8, 31)
    easy = make_problem(studied_concept, "easy-current", Problem.Difficulty.EASY)
    medium_one = make_problem(
        studied_concept, "medium-current-one", Problem.Difficulty.MEDIUM
    )
    medium_two = make_problem(
        studied_concept, "medium-current-two", Problem.Difficulty.MEDIUM
    )
    make_problem(studied_concept, "hard-not-eligible", Problem.Difficulty.HARD)

    pool = generate_saturday_assessment_pool(week_start)
    selections = list(pool.selections.select_related("problem"))

    assert len(selections) == 3
    assert [selection.slot_kind for selection in selections] == [
        AssessmentSelection.SlotKind.EASY,
        AssessmentSelection.SlotKind.MEDIUM,
        AssessmentSelection.SlotKind.MEDIUM,
    ]
    assert selections[0].problem_id == easy.pk
    assert {selection.problem_id for selection in selections} == {
        easy.pk,
        medium_one.pk,
        medium_two.pk,
    }
    assert len({selection.problem_id for selection in selections}) == 3
    assert pool.eligibility_metadata["selection_scope"] == (
        "current_week_studied_concepts"
    )
    assert pool.eligibility_metadata["selected_counts"] == {"easy": 1, "medium": 2}


@pytest.mark.django_db
def test_excludes_problems_from_unstudied_concepts(studied_concept):
    unstudied_concept = make_concept("hashing", "hashing-basics")
    make_problem(studied_concept, "studied-easy", Problem.Difficulty.EASY)
    make_problem(unstudied_concept, "unstudied-easy", Problem.Difficulty.EASY)
    for index in range(2):
        make_problem(
            studied_concept,
            f"studied-medium-{index}",
            Problem.Difficulty.MEDIUM,
        )
    make_problem(unstudied_concept, "unstudied-medium", Problem.Difficulty.MEDIUM)

    pool = generate_saturday_assessment_pool(date(2026, 8, 31))
    selected_ids = set(pool.selections.values_list("problem_id", flat=True))
    unstudied_ids = set(
        Problem.objects.filter(concept=unstudied_concept).values_list("id", flat=True)
    )

    assert selected_ids.isdisjoint(unstudied_ids)
    assert all(
        concept["name"] == studied_concept.name
        for selection in pool.selections.all()
        for concept in selection.eligibility_metadata["eligible_concepts"]
    )


@pytest.mark.django_db
def test_prefers_unseen_problem_within_each_difficulty(studied_concept):
    seen_easy = make_problem(
        studied_concept, "seen-easy", Problem.Difficulty.EASY, display_order=1
    )
    unseen_easy = make_problem(
        studied_concept, "unseen-easy", Problem.Difficulty.EASY, display_order=99
    )
    seen_medium = [
        make_problem(
            studied_concept,
            f"seen-medium-{index}",
            Problem.Difficulty.MEDIUM,
            display_order=index + 1,
        )
        for index in range(2)
    ]
    unseen_medium = make_problem(
        studied_concept, "unseen-medium", Problem.Difficulty.MEDIUM, display_order=99
    )
    ProblemLearningStatus.objects.create(
        problem=seen_easy,
        status=LearningStatus.SOLVED_INDEPENDENTLY,
        reason="I can reproduce it.",
    )
    for problem in seen_medium:
        ProblemLearningStatus.objects.create(
            problem=problem,
            status=LearningStatus.ATTEMPTED,
            reason="I need another recall pass.",
        )

    pool = generate_saturday_assessment_pool(date(2026, 8, 31))
    selected = list(pool.selections.select_related("problem"))

    assert selected[0].problem_id == unseen_easy.pk
    assert selected[0].is_unseen is True
    assert unseen_medium.pk in {item.problem_id for item in selected}
    assert sum(item.is_unseen for item in selected) == 2
    assert pool.eligibility_metadata["unseen_candidate_counts"] == {
        "easy": 1,
        "medium": 1,
    }


@pytest.mark.django_db
def test_a_pending_or_wrong_week_concept_does_not_count_as_studied(db):
    concept = make_concept("stacks", "stack-basics")
    mark_concept_studied(
        concept,
        date(2026, 8, 31),
        status=StudyBlock.Status.PENDING,
    )
    StudyBlock.objects.create(
        date=date(2026, 9, 9),
        week_start=date(2026, 9, 7),
        routine_key="2-concept",
        title="Learn one concept",
        planned_minutes=30,
        assigned_concept=concept,
        status=StudyBlock.Status.COMPLETED,
    )

    assert get_studied_concept_evidence(date(2026, 8, 31)) == {}


@pytest.mark.django_db
def test_sparse_pool_keeps_only_available_difficulty_slots_and_explains_gap(
    studied_concept,
):
    make_problem(studied_concept, "only-easy", Problem.Difficulty.EASY)

    pool = generate_saturday_assessment_pool(date(2026, 8, 31))

    assert pool.selections.count() == 1
    assert pool.selections.first().slot_kind == AssessmentSelection.SlotKind.EASY
    assert pool.is_sparse is True
    assert "sparse" in pool.rationale.casefold()
    assert pool.eligibility_metadata["fallback_included"] is False


@pytest.mark.django_db
def test_zero_preferred_pool_is_filled_entirely_from_older_concepts(studied_concept):
    older_concept = make_concept("hashing", "older-hashing", order=1)
    mark_concept_studied(older_concept, date(2026, 8, 24))
    older_easy = make_problem(older_concept, "older-easy", Problem.Difficulty.EASY)
    older_medium_one = make_problem(
        older_concept,
        "older-medium-one",
        Problem.Difficulty.MEDIUM,
    )
    older_medium_two = make_problem(
        older_concept,
        "older-medium-two",
        Problem.Difficulty.MEDIUM,
    )

    pool = generate_saturday_assessment_pool(date(2026, 8, 31))
    selections = list(pool.selections.select_related("problem"))

    assert {selection.problem_id for selection in selections} == {
        older_easy.pk,
        older_medium_one.pk,
        older_medium_two.pk,
    }
    assert all(selection.is_fallback for selection in selections)
    assert all("current-week" in selection.source_reason for selection in selections)
    assert pool.has_fallback is True
    assert pool.is_sparse is False
    assert pool.eligibility_metadata["current_week_selected_counts"] == {}
    assert pool.eligibility_metadata["fallback_selected_counts"] == {
        "easy": 1,
        "medium": 2,
    }


@pytest.mark.django_db
def test_partial_preferred_pool_fills_only_missing_difficulty_slots(studied_concept):
    current_easy = make_problem(
        studied_concept,
        "current-easy-only",
        Problem.Difficulty.EASY,
    )
    older_concept = make_concept("hashing", "older-partial", order=1)
    older_medium_one = make_problem(
        older_concept,
        "fallback-medium-one",
        Problem.Difficulty.MEDIUM,
    )
    older_medium_two = make_problem(
        older_concept,
        "fallback-medium-two",
        Problem.Difficulty.MEDIUM,
    )

    pool = generate_saturday_assessment_pool(date(2026, 8, 31))
    selections = list(pool.selections.select_related("problem"))

    assert [selection.problem_id for selection in selections] == [
        current_easy.pk,
        older_medium_one.pk,
        older_medium_two.pk,
    ]
    assert selections[0].is_fallback is False
    assert all(selection.is_fallback for selection in selections[1:])
    assert pool.eligibility_metadata["current_week_selected_counts"] == {"easy": 1}
    assert pool.eligibility_metadata["fallback_selected_counts"] == {
        "easy": 0,
        "medium": 2,
    }


@pytest.mark.django_db
def test_complete_preferred_pool_does_not_add_fallback_items(studied_concept):
    make_problem(studied_concept, "complete-easy", Problem.Difficulty.EASY)
    make_problem(studied_concept, "complete-medium-one", Problem.Difficulty.MEDIUM)
    make_problem(studied_concept, "complete-medium-two", Problem.Difficulty.MEDIUM)
    older_concept = make_concept("hashing", "unused-older", order=1)
    make_problem(older_concept, "unused-fallback", Problem.Difficulty.EASY)

    pool = generate_saturday_assessment_pool(date(2026, 8, 31))

    assert pool.selections.count() == 3
    assert pool.selections.filter(
        eligibility_metadata__source_kind=AssessmentSelection.SourceKind.OLDER_CONCEPT_FALLBACK
    ).count() == 0
    assert pool.eligibility_metadata["fallback_included"] is False


@pytest.mark.django_db
def test_regenerating_a_week_replaces_stale_selections_without_duplicates(
    studied_concept,
):
    for index in range(2):
        make_problem(
            studied_concept,
            f"medium-regeneration-{index}",
            Problem.Difficulty.MEDIUM,
        )
    make_problem(studied_concept, "easy-regeneration", Problem.Difficulty.EASY)

    first = generate_saturday_assessment_pool(date(2026, 8, 31))
    first_ids = set(first.selections.values_list("problem_id", flat=True))
    second = generate_saturday_assessment_pool(date(2026, 8, 31))

    assert first.pk == second.pk
    assert second.selections.count() == 3
    assert second.selections.values("problem_id").distinct().count() == 3
    assert set(second.selections.values_list("problem_id", flat=True)) == first_ids
