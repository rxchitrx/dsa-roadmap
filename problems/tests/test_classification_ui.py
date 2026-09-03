import pytest
from django.test import override_settings
from django.urls import reverse

from curriculum.models import Concept, Topic

from problems.models import Problem, ProblemClassification


@pytest.fixture
def classification_problem(db):
    topic = Topic.objects.create(
        name="Arrays",
        slug="ui-classification-arrays",
        description="Classification UI concepts",
    )
    concepts = [
        Concept.objects.create(
            topic=topic,
            name=name,
            slug=slug,
            order=order,
            summary="A concept.",
            intuition="An intuition.",
            explanation="An explanation.",
            complexity_notes="O(n)",
            implementation_guidance="An invariant.",
            common_traps="An edge case.",
            guided_practice="Trace it.",
            checkpoint="Explain it.",
        )
        for order, (name, slug) in enumerate(
            (("Traversal", "ui-traversal"), ("Two Pointers", "ui-two-pointers")),
            start=1,
        )
    ]
    problem = Problem.objects.create(
        concept=concepts[0],
        title="Classification UI problem",
        slug="classification-ui-problem",
        statement="A problem for testing visible Concept tags.",
        difficulty=Problem.Difficulty.EASY,
        source_name="Fixture source",
    )
    return problem, concepts


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="problems.tests.urls")
def test_problem_detail_shows_classifications_and_add_form(client, classification_problem):
    problem, concepts = classification_problem

    response = client.get(reverse("problems:detail", kwargs={"slug": problem.slug}))

    assert response.status_code == 200
    assert "Traversal" in response.content.decode()
    assert "Confirmed" in response.content.decode()
    assert "Add Concept tag" in response.content.decode()
    assert response.context["classification_form"].fields["concept"].queryset.filter(
        pk=concepts[1].pk
    ).exists()


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="problems.tests.urls")
def test_problem_detail_can_add_warning_classification(client, classification_problem):
    problem, concepts = classification_problem

    response = client.post(
        reverse("problems:classification_add", kwargs={"slug": problem.slug}),
        {
            "concept": concepts[1].pk,
            "status": ProblemClassification.Status.UNCERTAIN,
            "note": "The statement could support either pattern.",
        },
    )

    assert response.status_code == 302
    classification = ProblemClassification.objects.get(problem=problem, concept=concepts[1])
    assert classification.status == ProblemClassification.Status.UNCERTAIN
    detail = client.get(reverse("problems:detail", kwargs={"slug": problem.slug}))
    assert detail.status_code == 200
    assert 'data-testid="classification-warning"' in detail.content.decode()
    assert "The statement could support either pattern." in detail.content.decode()


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="problems.tests.urls")
def test_problem_detail_rejects_warning_without_reason_and_can_remove_tag(
    client, classification_problem
):
    problem, concepts = classification_problem

    invalid = client.post(
        reverse("problems:classification_add", kwargs={"slug": problem.slug}),
        {
            "concept": concepts[1].pk,
            "status": ProblemClassification.Status.FALLBACK,
            "note": "",
        },
    )
    assert invalid.status_code == 400
    assert "Add a reason" in invalid.content.decode()

    classification = ProblemClassification.objects.create(
        problem=problem,
        concept=concepts[1],
        status=ProblemClassification.Status.CONFIRMED,
    )
    removed = client.post(
        reverse(
            "problems:classification_remove",
            kwargs={"slug": problem.slug, "classification_id": classification.pk},
        )
    )
    assert removed.status_code == 302
    assert not ProblemClassification.objects.filter(pk=classification.pk).exists()
