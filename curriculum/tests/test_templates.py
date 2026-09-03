import pytest
from django.core.management import call_command
from django.urls import reverse

from curriculum.models import Concept


@pytest.fixture
def seeded_curriculum(db):
    call_command("seed_curriculum", verbosity=0)


@pytest.mark.django_db
def test_concept_lesson_renders_all_core_learning_sections(client, seeded_curriculum):
    concept = Concept.objects.get(slug="two-pointers")
    response = client.get(
        reverse("curriculum:concept_detail", kwargs={"concept_slug": concept.slug})
    )
    html = response.content.decode()

    assert 'data-testid="concept-lesson"' in html
    assert "Arrays &amp; Strings" in html
    assert "Why this matters" in html
    assert "Examples" in html
    assert "Complexity" in html
    assert "Implementation guidance" in html
    assert "Common traps" in html
    assert "Guided practice" in html
    assert "Checkpoint" in html
    assert "Two sum in a sorted array" in html
    assert "while left &lt; right" in html


@pytest.mark.django_db
def test_curriculum_index_links_to_each_concept_lesson(client, seeded_curriculum):
    response = client.get(reverse("curriculum:index"))
    html = response.content.decode()

    assert reverse(
        "curriculum:concept_detail", kwargs={"concept_slug": "array-fundamentals"}
    ) in html
    assert reverse(
        "curriculum:concept_detail", kwargs={"concept_slug": "two-pointers"}
    ) in html
