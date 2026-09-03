import pytest
from django.core.management import call_command
from django.urls import reverse

from curriculum.models import Concept


@pytest.fixture
def seeded_curriculum(db):
    call_command("seed_curriculum", verbosity=0)


@pytest.mark.django_db
def test_curriculum_index_browses_topics_and_ordered_concepts(client, seeded_curriculum):
    response = client.get(reverse("curriculum:index"))

    assert response.status_code == 200
    assert response.context["topics"].count() == 1
    html = response.content.decode()
    assert "Arrays &amp; Strings" in html
    assert html.index("Array Fundamentals") < html.index("Array Traversal")
    assert html.index("Array Traversal") < html.index("Two Pointers")


@pytest.mark.django_db
def test_concept_detail_loads_lesson_and_topic_context(client, seeded_curriculum):
    concept = Concept.objects.get(slug="two-pointers")

    response = client.get(
        reverse("curriculum:concept_detail", kwargs={"concept_slug": concept.slug})
    )

    assert response.status_code == 200
    assert response.context["concept"].pk == concept.pk
    assert response.context["concept"].topic.slug == "arrays-strings"
    assert response.context["concept"].prerequisites.all()[0].slug == "array-traversal"


@pytest.mark.django_db
def test_unknown_concept_returns_not_found(client, seeded_curriculum):
    response = client.get(
        reverse("curriculum:concept_detail", kwargs={"concept_slug": "does-not-exist"})
    )

    assert response.status_code == 404
