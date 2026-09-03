import pytest

from curriculum.models import Concept, Topic


@pytest.fixture
def concept(db):
    topic = Topic.objects.create(
        name="Arrays & Strings",
        slug="arrays-strings",
        description="Foundational sequence patterns.",
    )
    return Concept.objects.create(
        topic=topic,
        name="Array Fundamentals",
        slug="array-fundamentals",
        order=1,
        summary="Build reliable sequence intuition.",
        intuition="Arrays keep values in an ordered sequence.",
        explanation="Indexing gives direct access to a position.",
        examples=[],
        complexity_notes="Indexing is O(1).",
        implementation_guidance="Name the invariant before coding.",
        common_traps="Do not confuse values with indices.",
        guided_practice="Trace one array by hand.",
        checkpoint="Explain the invariant.",
    )
