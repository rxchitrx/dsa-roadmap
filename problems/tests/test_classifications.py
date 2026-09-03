import pytest
from django.core.exceptions import ValidationError

from curriculum.models import Concept, Topic

from problems.forms import ProblemClassificationForm
from problems.models import Problem, ProblemClassification
from problems.services import (
    add_classification,
    classification_warning_state,
    remove_classification,
)


@pytest.fixture
def concepts(db):
    topic = Topic.objects.create(
        name="Arrays",
        slug="classification-arrays",
        description="Classification test concepts",
    )
    return [
        Concept.objects.create(
            topic=topic,
            name=name,
            slug=slug,
            order=order,
            summary="A concept.",
            intuition="An intuition.",
            explanation="An explanation.",
            complexity_notes="O(n)",
            implementation_guidance="Write an invariant.",
            common_traps="Off-by-one.",
            guided_practice="Trace it.",
            checkpoint="Explain it.",
        )
        for order, (slug, name) in enumerate(
            (
                ("classification-traversal", "Traversal"),
                ("classification-two-pointers", "Two Pointers"),
                ("classification-hashing", "Hashing"),
            ),
            start=1,
        )
    ]


@pytest.fixture
def problem(db):
    return Problem.objects.create(
        title="Classification fixture",
        slug="classification-fixture",
        statement="Classify this problem without rewriting source metadata.",
        difficulty=Problem.Difficulty.MEDIUM,
        source_name="Fixture Source",
        source_problem_id="fixture-1",
        source_url="https://example.com/problems/classification-fixture",
    )


@pytest.mark.django_db
def test_add_classification_supports_multiple_concepts_and_preserves_source(problem, concepts):
    original_source = (
        problem.source_name,
        problem.source_problem_id,
        problem.source_url,
        problem.statement,
    )

    first = add_classification(problem, concepts[0])
    second = add_classification(
        problem,
        concepts[1],
        status=ProblemClassification.Status.CONFIRMED,
    )

    assert {item.concept_id for item in problem.classifications.all()} == {
        concepts[0].id,
        concepts[1].id,
    }
    problem.refresh_from_db()
    assert problem.concept_id == concepts[0].id
    assert (
        problem.source_name,
        problem.source_problem_id,
        problem.source_url,
        problem.statement,
    ) == original_source
    assert first.status == ProblemClassification.Status.CONFIRMED
    assert second.status == ProblemClassification.Status.CONFIRMED
    assert set(problem.concepts.values_list("id", flat=True)) == {
        concepts[0].id,
        concepts[1].id,
    }


@pytest.mark.django_db
def test_primary_concept_save_is_backfilled_as_confirmed_classification(concepts):
    problem = Problem.objects.create(
        concept=concepts[0],
        title="Seed-style problem",
        slug="seed-style-problem",
        statement="Written by the existing catalog seed shape.",
    )

    classification = problem.classifications.get()
    assert classification.concept_id == concepts[0].id
    assert classification.status == ProblemClassification.Status.CONFIRMED
    assert list(problem.concepts.all()) == [concepts[0]]


@pytest.mark.django_db
def test_remove_classification_promotes_remaining_concept_and_can_clear_last(problem, concepts):
    add_classification(problem, concepts[0])
    add_classification(problem, concepts[1])

    assert remove_classification(problem, concepts[0]) is True
    problem.refresh_from_db()
    assert problem.concept_id == concepts[1].id
    assert list(problem.classifications.values_list("concept_id", flat=True)) == [concepts[1].id]

    assert remove_classification(problem, concepts[1]) is True
    problem.refresh_from_db()
    assert problem.concept_id is None
    assert problem.classifications.count() == 0
    assert remove_classification(problem, concepts[1]) is False


@pytest.mark.django_db
def test_uncertain_and_fallback_classifications_expose_explicit_warning(problem, concepts):
    uncertain = add_classification(
        problem,
        concepts[0],
        status=ProblemClassification.Status.UNCERTAIN,
        note="The statement suggests traversal, but the invariant is not clear yet.",
    )

    assert uncertain.is_warning is True
    assert problem.classification_warning_state == ProblemClassification.Status.UNCERTAIN
    assert classification_warning_state(problem) == ProblemClassification.Status.UNCERTAIN
    assert problem.has_classification_warning is True
    assert "Concept classification is uncertain" in problem.metadata_warnings

    add_classification(
        problem,
        concepts[1],
        status=ProblemClassification.Status.FALLBACK,
        note="Use the nearest studied concept until the catalog is reviewed.",
    )
    assert problem.classification_warning_state == "uncertain_and_fallback"
    assert problem.metadata_warnings == [
        "Concept classification is uncertain",
        "Concept classification uses a fallback",
    ]


@pytest.mark.django_db
def test_warning_classification_requires_a_reason(problem, concepts):
    with pytest.raises(ValidationError, match="reason"):
        add_classification(
            problem,
            concepts[0],
            status=ProblemClassification.Status.FALLBACK,
        )

    classification = ProblemClassification(
        problem=problem,
        concept=concepts[0],
        status=ProblemClassification.Status.UNCERTAIN,
    )
    with pytest.raises(ValidationError, match="reason"):
        classification.full_clean()


@pytest.mark.django_db
def test_classification_form_rejects_duplicate_and_missing_warning_reason(problem, concepts):
    add_classification(problem, concepts[0])

    duplicate_form = ProblemClassificationForm(
        data={"concept": concepts[0].pk, "status": "confirmed", "note": ""},
        problem=problem,
    )
    assert duplicate_form.is_valid() is False
    assert "already classified" in str(duplicate_form.errors)

    warning_form = ProblemClassificationForm(
        data={"concept": concepts[1].pk, "status": "uncertain", "note": "  "},
        problem=problem,
    )
    assert warning_form.is_valid() is False
    assert "reason" in str(warning_form.errors)
