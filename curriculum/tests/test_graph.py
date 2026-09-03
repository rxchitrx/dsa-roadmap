import pytest
from django.core.management import call_command
from django.urls import reverse

from curriculum.models import Concept
from curriculum.services import (
    PrerequisiteGraphError,
    add_prerequisite,
    remove_prerequisite,
)


@pytest.fixture
def seeded_curriculum(db):
    call_command("seed_curriculum", verbosity=0)


@pytest.mark.django_db
def test_graph_service_adds_and_removes_direct_edges(seeded_curriculum):
    fundamentals = Concept.objects.get(slug="array-fundamentals")
    two_pointers = Concept.objects.get(slug="two-pointers")
    two_pointers.prerequisites.clear()

    assert add_prerequisite(concept=two_pointers, prerequisite=fundamentals) is True
    assert list(two_pointers.prerequisites.values_list("slug", flat=True)) == [
        "array-fundamentals"
    ]
    assert add_prerequisite(concept=two_pointers, prerequisite=fundamentals) is False

    assert remove_prerequisite(
        concept=two_pointers, prerequisite=fundamentals
    ) is True
    assert list(two_pointers.prerequisites.all()) == []
    assert remove_prerequisite(
        concept=two_pointers, prerequisite=fundamentals
    ) is False


@pytest.mark.django_db
def test_graph_service_rejects_self_links_and_direct_cycles(seeded_curriculum):
    fundamentals = Concept.objects.get(slug="array-fundamentals")
    traversal = Concept.objects.get(slug="array-traversal")

    with pytest.raises(PrerequisiteGraphError, match="own prerequisite"):
        add_prerequisite(concept=fundamentals, prerequisite=fundamentals)

    with pytest.raises(PrerequisiteGraphError, match="prerequisite cycle"):
        add_prerequisite(concept=fundamentals, prerequisite=traversal)

    assert list(fundamentals.prerequisites.all()) == []


@pytest.mark.django_db
def test_graph_service_rejects_indirect_cycles(seeded_curriculum):
    fundamentals = Concept.objects.get(slug="array-fundamentals")
    traversal = Concept.objects.get(slug="array-traversal")
    two_pointers = Concept.objects.get(slug="two-pointers")

    # Existing seed edges are two_pointers -> traversal -> fundamentals.
    with pytest.raises(PrerequisiteGraphError, match="prerequisite cycle"):
        add_prerequisite(concept=fundamentals, prerequisite=two_pointers)


@pytest.mark.django_db
def test_graph_page_displays_direct_prerequisites_and_edit_controls(
    client, seeded_curriculum
):
    response = client.get(reverse("curriculum:prerequisite_graph"))

    assert response.status_code == 200
    html = response.content.decode()
    assert 'data-testid="prerequisite-graph"' in html
    assert "Direct prerequisites" in html
    assert "Array Traversal" in html
    assert "Two Pointers" in html
    assert reverse("curriculum:graph_add") in html
    assert reverse("curriculum:graph_remove") in html


@pytest.mark.django_db
def test_add_edge_route_persists_edge_and_redirects(client, seeded_curriculum):
    fundamentals = Concept.objects.get(slug="array-fundamentals")
    two_pointers = Concept.objects.get(slug="two-pointers")
    traversal = Concept.objects.get(slug="array-traversal")
    two_pointers.prerequisites.remove(traversal)

    response = client.post(
        reverse("curriculum:graph_add"),
        {"concept_id": two_pointers.pk, "prerequisite_id": fundamentals.pk},
    )

    assert response.status_code == 302
    assert response.url == reverse("curriculum:prerequisite_graph")
    assert two_pointers.prerequisites.filter(pk=fundamentals.pk).exists()

    page = client.get(response.url)
    assert "Prerequisite added" in page.content.decode()


@pytest.mark.django_db
def test_remove_edge_route_persists_removal(client, seeded_curriculum):
    fundamentals = Concept.objects.get(slug="array-fundamentals")
    traversal = Concept.objects.get(slug="array-traversal")

    response = client.post(
        reverse("curriculum:graph_remove"),
        {"concept_id": traversal.pk, "prerequisite_id": fundamentals.pk},
    )

    assert response.status_code == 302
    assert not traversal.prerequisites.filter(pk=fundamentals.pk).exists()

    page = client.get(response.url)
    assert "Prerequisite removed" in page.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("concept_slug", "prerequisite_slug", "message"),
    [
        (
            "array-fundamentals",
            "array-fundamentals",
            "own prerequisite",
        ),
        ("array-fundamentals", "array-traversal", "prerequisite cycle"),
    ],
)
def test_add_edge_route_shows_actionable_validation_feedback(
    client, seeded_curriculum, concept_slug, prerequisite_slug, message
):
    concept = Concept.objects.get(slug=concept_slug)
    prerequisite = Concept.objects.get(slug=prerequisite_slug)

    response = client.post(
        reverse("curriculum:graph_add"),
        {"concept_id": concept.pk, "prerequisite_id": prerequisite.pk},
    )

    assert response.status_code == 302
    page = client.get(response.url)
    assert message in page.content.decode()
    assert not concept.prerequisites.filter(pk=prerequisite.pk).exists()


@pytest.mark.django_db
def test_graph_page_links_from_curriculum_index_and_lesson(
    client, seeded_curriculum
):
    index_html = client.get(reverse("curriculum:index")).content.decode()
    lesson_html = client.get(
        reverse(
            "curriculum:concept_detail",
            kwargs={"concept_slug": "two-pointers"},
        )
    ).content.decode()

    assert reverse("curriculum:prerequisite_graph") in index_html
    assert reverse("curriculum:prerequisite_graph") in lesson_html
