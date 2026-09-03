import pytest

from curriculum.models import Concept, Topic

from problems.models import Problem


@pytest.mark.django_db
def test_problem_can_keep_missing_catalog_metadata():
    problem = Problem.objects.create(
        title="Personal warm-up",
        slug="personal-warm-up",
        statement="Trace the values before writing code.",
    )

    assert problem.has_metadata_warning is True
    assert problem.metadata_warnings == [
        "Needs concept classification",
        "Difficulty not set",
        "Source not set",
    ]


@pytest.mark.django_db
def test_problem_is_connected_to_the_curriculum_concept():
    topic = Topic.objects.create(
        name="Arrays",
        slug="arrays",
        description="Array problems",
    )
    concept = Concept.objects.create(
        topic=topic,
        name="Traversal",
        slug="traversal",
        order=1,
        summary="Scan with an invariant.",
        intuition="Move a boundary.",
        explanation="Keep a useful accumulator.",
        complexity_notes="O(n)",
        implementation_guidance="State the invariant.",
        common_traps="Off by one.",
        guided_practice="Trace it.",
        checkpoint="What is true after index i?",
    )
    problem = Problem.objects.create(
        concept=concept,
        title="Running maximum",
        slug="running-maximum",
        statement="Return the maximum value.",
        difficulty=Problem.Difficulty.EASY,
        source_name="Practice",
    )

    assert problem.concept == concept
    assert list(concept.problems.all()) == [problem]
