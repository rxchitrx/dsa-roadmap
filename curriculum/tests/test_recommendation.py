from datetime import timedelta

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from curriculum.models import Concept, Topic
from curriculum.services import recommend_next_concept
from progress.models import ConceptCheckpoint


@pytest.fixture
def seeded_curriculum(db):
    call_command("seed_curriculum", verbosity=0)


def checkpoint(concept, *, confidence, submitted_at=None):
    record = ConceptCheckpoint.objects.create(
        concept=concept,
        confidence=confidence,
        recall_response="I can state the invariant and a first implementation step.",
    )
    if submitted_at is not None:
        ConceptCheckpoint.objects.filter(pk=record.pk).update(submitted_at=submitted_at)
        record.submitted_at = submitted_at
    return record


@pytest.mark.django_db
def test_concept_model_prerequisite_edge_requires_checkpoint_evidence_to_be_ready(
    seeded_curriculum,
):
    fundamentals = Concept.objects.get(slug="array-fundamentals")
    traversal = Concept.objects.get(slug="array-traversal")
    now = timezone.now()

    assert recommend_next_concept(now=now).concept == fundamentals

    checkpoint(
        fundamentals,
        confidence=ConceptCheckpoint.Confidence.DEVELOPING,
        submitted_at=now,
    )
    assert recommend_next_concept(now=now).concept == fundamentals

    checkpoint(
        fundamentals,
        confidence=ConceptCheckpoint.Confidence.SOLID,
        submitted_at=now,
    )
    assert recommend_next_concept(now=now).concept == traversal


@pytest.mark.django_db
def test_recommendation_uses_latest_checkpoint_confidence_and_weak_evidence_first(db):
    topic = Topic.objects.create(
        name="Arrays",
        slug="arrays",
        description="Array patterns.",
    )
    first = _make_concept(topic, name="First", slug="first", order=1)
    second = _make_concept(topic, name="Second", slug="second", order=2)
    now = timezone.now()

    checkpoint(first, confidence=ConceptCheckpoint.Confidence.CONFIDENT, submitted_at=now)
    checkpoint(second, confidence=ConceptCheckpoint.Confidence.DEVELOPING, submitted_at=now)
    checkpoint(second, confidence=ConceptCheckpoint.Confidence.SOLID, submitted_at=now)

    recommendation = recommend_next_concept(now=now)

    assert recommendation is not None
    assert recommendation.concept == second
    assert "Latest checkpoint confidence: Solid enough to practice (3/5)." in recommendation.evidence


@pytest.mark.django_db
def test_recommendation_uses_recency_after_confidence_tie(db):
    topic = Topic.objects.create(
        name="Arrays",
        slug="arrays",
        description="Array patterns.",
    )
    old = _make_concept(topic, name="Old", slug="old", order=1)
    recent = _make_concept(topic, name="Recent", slug="recent", order=2)
    now = timezone.now()

    checkpoint(
        old,
        confidence=ConceptCheckpoint.Confidence.SOLID,
        submitted_at=now - timedelta(days=30),
    )
    checkpoint(
        recent,
        confidence=ConceptCheckpoint.Confidence.SOLID,
        submitted_at=now - timedelta(days=2),
    )

    recommendation = recommend_next_concept(now=now)

    assert recommendation is not None
    assert recommendation.concept == old
    assert "30 days old" in " ".join(recommendation.evidence)


@pytest.mark.django_db
def test_recommendation_prioritizes_missing_coverage_deterministically(db):
    topic = Topic.objects.create(
        name="Arrays",
        slug="arrays",
        description="Array patterns.",
    )
    covered = _make_concept(topic, name="Covered", slug="covered", order=1)
    uncovered = _make_concept(topic, name="Uncovered", slug="uncovered", order=2)
    now = timezone.now()
    checkpoint(covered, confidence=ConceptCheckpoint.Confidence.DEVELOPING, submitted_at=now)

    recommendation = recommend_next_concept(now=now)

    assert recommendation is not None
    assert recommendation.concept == uncovered
    assert "missing coverage" in " ".join(recommendation.evidence)


@pytest.mark.django_db
def test_recommendation_returns_none_when_every_concept_is_confident_and_recent(db):
    topic = Topic.objects.create(
        name="Arrays",
        slug="arrays",
        description="Array patterns.",
    )
    first = _make_concept(topic, name="First", slug="first", order=1)
    second = _make_concept(topic, name="Second", slug="second", order=2)
    now = timezone.now()
    checkpoint(first, confidence=ConceptCheckpoint.Confidence.CONFIDENT, submitted_at=now)
    checkpoint(second, confidence=ConceptCheckpoint.Confidence.TEACHABLE, submitted_at=now)

    assert recommend_next_concept(now=now) is None


@pytest.mark.django_db
def test_recommendation_route_renders_selected_concept_and_evidence(
    client, seeded_curriculum
):
    fundamentals = Concept.objects.get(slug="array-fundamentals")
    checkpoint(
        fundamentals,
        confidence=ConceptCheckpoint.Confidence.SOLID,
        submitted_at=timezone.now(),
    )

    response = client.get(reverse("curriculum:recommendation"))

    assert response.status_code == 200
    assert response.context["recommendation"].concept.slug == "array-traversal"
    html = response.content.decode()
    assert 'data-testid="concept-recommendation"' in html
    assert 'data-testid="recommendation-result"' in html
    assert "Array Traversal" in html
    assert "Why this is next" in html
    assert "Prerequisites ready: Array Fundamentals" in html
    assert reverse(
        "curriculum:concept_detail", kwargs={"concept_slug": "array-traversal"}
    ) in html


@pytest.mark.django_db
def test_recommendation_route_renders_no_eligible_concept_state(
    client, seeded_curriculum
):
    now = timezone.now()
    for concept in Concept.objects.all():
        checkpoint(
            concept,
            confidence=ConceptCheckpoint.Confidence.CONFIDENT,
            submitted_at=now,
        )

    response = client.get(reverse("curriculum:recommendation"))

    assert response.status_code == 200
    assert response.context["recommendation"] is None
    html = response.content.decode()
    assert 'data-testid="recommendation-empty"' in html
    assert "No Concept needs attention right now." in html


def _make_concept(topic, *, name, slug, order):
    return Concept.objects.create(
        topic=topic,
        name=name,
        slug=slug,
        order=order,
        summary="A short lesson summary.",
        intuition="A useful mental model.",
        explanation="A complete explanation.",
        examples=[],
        complexity_notes="O(n) time and O(1) space.",
        implementation_guidance="State the invariant before coding.",
        common_traps="Do not skip edge cases.",
        guided_practice="Trace one example by hand.",
        checkpoint="Explain the invariant.",
    )
