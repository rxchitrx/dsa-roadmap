import pytest
from curriculum.models import Concept, Topic

from problems.management.commands.seed_problems import Command
from problems.models import Problem


@pytest.fixture
def seeded_curriculum(db):
    topic = Topic.objects.create(
        name="Arrays & Strings",
        slug="arrays-strings",
        description="Foundations",
    )
    for order, slug, name in [
        (1, "array-fundamentals", "Array Fundamentals"),
        (2, "array-traversal", "Array Traversal"),
        (3, "two-pointers", "Two Pointers"),
    ]:
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


@pytest.mark.django_db
def test_seed_problems_is_idempotent_and_uses_concepts(seeded_curriculum):
    command = Command()
    command.handle()
    command.handle()

    assert Problem.objects.count() == 6
    assert Problem.objects.filter(concept__isnull=False).count() == 6
    assert Problem.objects.get(slug="two-sum-ii-input-array-is-sorted").concept.slug == "two-pointers"
