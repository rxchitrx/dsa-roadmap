import pytest
from django.db import IntegrityError

from curriculum.models import Concept, Topic


def make_concept(topic, *, name="Arrays", slug="arrays", order=1):
    return Concept.objects.create(
        topic=topic,
        name=name,
        slug=slug,
        order=order,
        summary="A short lesson summary.",
        intuition="A useful mental model.",
        explanation="A complete explanation.",
        examples=[{"title": "Example", "input": "[]", "output": "[]"}],
        complexity_notes="O(n) time and O(1) space.",
        implementation_guidance="State the invariant before coding.",
        common_traps="Do not skip edge cases.",
        guided_practice="Trace one example by hand.",
        checkpoint="Explain the invariant.",
    )


@pytest.mark.django_db
def test_topic_orders_concepts_and_concepts_can_declare_prerequisites():
    topic = Topic.objects.create(
        name="Arrays & Strings",
        slug="arrays-strings",
        description="Foundational sequence patterns.",
    )
    first = make_concept(topic, name="Array Fundamentals", slug="array-fundamentals")
    second = make_concept(
        topic,
        name="Two Pointers",
        slug="two-pointers",
        order=2,
    )
    second.prerequisites.add(first)

    assert list(topic.concepts.values_list("slug", flat=True)) == [
        "array-fundamentals",
        "two-pointers",
    ]
    assert list(second.prerequisites.all()) == [first]
    assert str(topic) == "Arrays & Strings"
    assert str(second) == "Arrays & Strings: Two Pointers"


@pytest.mark.django_db
def test_concept_order_is_unique_inside_a_topic_but_not_across_topics():
    first_topic = Topic.objects.create(
        name="Arrays",
        slug="arrays",
        description="Arrays.",
    )
    second_topic = Topic.objects.create(
        name="Hashing",
        slug="hashing",
        description="Hashing.",
    )
    make_concept(first_topic)
    make_concept(second_topic, slug="hashing-basics")

    with pytest.raises(IntegrityError):
        make_concept(first_topic, slug="another-arrays-concept")
