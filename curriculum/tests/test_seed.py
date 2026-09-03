from io import StringIO

import pytest
from django.core.management import call_command

from curriculum.models import Concept, Topic


@pytest.mark.django_db
def test_seed_creates_ordered_concepts_and_prerequisite_chain():
    output = StringIO()

    call_command("seed_curriculum", stdout=output)

    topic = Topic.objects.get(slug="arrays-strings")
    concepts = list(topic.concepts.all())

    assert [concept.slug for concept in concepts] == [
        "array-fundamentals",
        "array-traversal",
        "two-pointers",
    ]
    assert list(concepts[1].prerequisites.values_list("slug", flat=True)) == [
        "array-fundamentals",
    ]
    assert list(concepts[2].prerequisites.values_list("slug", flat=True)) == [
        "array-traversal",
    ]
    assert "Seeded Arrays & Strings with 3 ordered concepts." in output.getvalue()


@pytest.mark.django_db
def test_seed_is_idempotent_and_keeps_original_lesson_content():
    call_command("seed_curriculum", verbosity=0)
    first_count = (Topic.objects.count(), Concept.objects.count())
    first_explanation = Concept.objects.get(slug="two-pointers").explanation

    call_command("seed_curriculum", verbosity=0)

    assert (Topic.objects.count(), Concept.objects.count()) == first_count
    assert Concept.objects.get(slug="two-pointers").explanation == first_explanation
