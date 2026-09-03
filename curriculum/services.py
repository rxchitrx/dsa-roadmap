from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db.models import QuerySet
from django.db import transaction
from django.utils import timezone

from progress.models import ConceptCheckpoint

from .models import Concept


class PrerequisiteGraphError(ValueError):
    """Raised when a requested prerequisite edge is not valid."""


PREREQUISITE_READY_CONFIDENCE = ConceptCheckpoint.Confidence.SOLID
CONFIDENT_ENOUGH = ConceptCheckpoint.Confidence.CONFIDENT
STALE_AFTER = timedelta(days=14)


@dataclass(frozen=True)
class ConceptRecommendation:
    """A deterministic next-concept choice with learner-facing evidence."""

    concept: Concept
    reason: str
    evidence: tuple[str, ...]


def _latest_checkpoints(concept_ids: list[int]) -> dict[int, ConceptCheckpoint]:
    """Return the newest checkpoint model row for each requested Concept."""

    latest: dict[int, ConceptCheckpoint] = {}
    checkpoints = ConceptCheckpoint.objects.filter(
        concept_id__in=concept_ids
    ).order_by("concept_id", "-submitted_at", "-id")
    for checkpoint in checkpoints:
        latest.setdefault(checkpoint.concept_id, checkpoint)
    return latest


def _age_days(checkpoint: ConceptCheckpoint, now: datetime) -> int:
    elapsed = max(0, (now - checkpoint.submitted_at).total_seconds())
    return int(elapsed // timedelta(days=1).total_seconds())


def _prerequisites_are_ready(
    concept: Concept,
    latest_checkpoints: dict[int, ConceptCheckpoint],
) -> bool:
    """A Concept is gated until every prerequisite has solid checkpoint evidence."""

    return all(
        (
            checkpoint := latest_checkpoints.get(prerequisite.pk)
        ) is not None
        and checkpoint.confidence >= PREREQUISITE_READY_CONFIDENCE
        for prerequisite in concept.prerequisites.all()
    )


def _needs_attention(
    checkpoint: ConceptCheckpoint | None,
    *,
    now: datetime,
) -> bool:
    if checkpoint is None:
        return True
    return (
        checkpoint.confidence < CONFIDENT_ENOUGH
        or now - checkpoint.submitted_at >= STALE_AFTER
    )


def _ranking_key(
    concept: Concept,
    checkpoint: ConceptCheckpoint | None,
    *,
    now: datetime,
) -> tuple[int, int, int, int, int, int]:
    """Rank coverage first, then confidence gap, then stale evidence.

    The final curriculum-order fields make ties stable even when two Concepts
    have identical evidence.
    """

    missing_coverage = int(checkpoint is None)
    confidence_gap = (
        0 if checkpoint is None else int(CONFIDENT_ENOUGH - checkpoint.confidence)
    )
    recency_days = 0 if checkpoint is None else _age_days(checkpoint, now)
    return (
        -missing_coverage,
        -confidence_gap,
        -recency_days,
        concept.topic.display_order,
        concept.order,
        concept.pk,
    )


def _recommendation_copy(
    concept: Concept,
    checkpoint: ConceptCheckpoint | None,
    latest_checkpoints: dict[int, ConceptCheckpoint],
    *,
    now: datetime,
) -> tuple[str, tuple[str, ...]]:
    evidence: list[str] = []

    if checkpoint is None:
        evidence.append("No checkpoint is logged yet, so this Concept has missing coverage.")
        reason = "It is the earliest ready Concept that still needs coverage."
    else:
        confidence_label = checkpoint.get_confidence_display()
        evidence.append(
            f"Latest checkpoint confidence: {confidence_label} ({checkpoint.confidence}/5)."
        )
        age_days = _age_days(checkpoint, now)
        evidence.append(f"The latest checkpoint is {age_days} days old.")
        if checkpoint.confidence < CONFIDENT_ENOUGH:
            evidence.append("Confidence is below Confident, so another learning pass is useful.")
            reason = "Its latest checkpoint shows the weakest confidence among ready Concepts."
        elif age_days >= STALE_AFTER.days:
            evidence.append(
                f"The latest checkpoint is {age_days} days old, so its evidence is stale."
            )
            reason = "Its checkpoint is the stalest ready evidence that needs a refresh."
        else:
            reason = "It is the highest-priority ready Concept in the curriculum order."

    prerequisites = list(concept.prerequisites.all())
    if prerequisites:
        ready_names = []
        for prerequisite in prerequisites:
            prerequisite_checkpoint = latest_checkpoints[prerequisite.pk]
            ready_names.append(
                f"{prerequisite.name} ({prerequisite_checkpoint.get_confidence_display()})"
            )
        evidence.append("Prerequisites ready: " + ", ".join(ready_names) + ".")
    else:
        evidence.append("No prerequisites are blocking this Concept.")

    return reason, tuple(evidence)


def recommend_next_concept(
    concepts: QuerySet[Concept] | list[Concept] | None = None,
    *,
    now: datetime | None = None,
) -> ConceptRecommendation | None:
    """Choose one ready Concept that needs the next learning pass.

    A Concept is eligible only when all of its prerequisites have a latest
    checkpoint at ``Solid enough to practice`` or above. Concepts with no
    checkpoint, low confidence, or stale evidence are candidates; confident,
    recent Concepts are intentionally left alone until their evidence needs
    attention again.
    """

    now = now or timezone.now()
    if concepts is None:
        concepts = Concept.objects.select_related("topic").prefetch_related(
            "prerequisites"
        )
    concept_list = list(concepts)
    if not concept_list:
        return None

    related_concept_ids = {
        prerequisite.pk
        for concept in concept_list
        for prerequisite in concept.prerequisites.all()
    }
    latest_checkpoints = _latest_checkpoints(
        [concept.pk for concept in concept_list] + list(related_concept_ids)
    )
    candidates = [
        concept
        for concept in concept_list
        if _prerequisites_are_ready(concept, latest_checkpoints)
        and _needs_attention(latest_checkpoints.get(concept.pk), now=now)
    ]
    if not candidates:
        return None

    selected = min(
        candidates,
        key=lambda concept: _ranking_key(
            concept,
            latest_checkpoints.get(concept.pk),
            now=now,
        ),
    )
    reason, evidence = _recommendation_copy(
        selected,
        latest_checkpoints.get(selected.pk),
        latest_checkpoints,
        now=now,
    )
    return ConceptRecommendation(
        concept=selected,
        reason=reason,
        evidence=evidence,
    )


def _has_prerequisite_path(start: Concept, target: Concept) -> bool:
    """Return whether ``start`` reaches ``target`` through prerequisites."""

    pending = [start.pk]
    visited: set[int] = set()

    while pending:
        concept_id = pending.pop()
        if concept_id in visited:
            continue
        visited.add(concept_id)

        prerequisite_ids = Concept.objects.filter(pk=concept_id).values_list(
            "prerequisites__pk", flat=True
        )
        for prerequisite_id in prerequisite_ids:
            if prerequisite_id is None:
                continue
            if prerequisite_id == target.pk:
                return True
            if prerequisite_id not in visited:
                pending.append(prerequisite_id)

    return False


@transaction.atomic
def add_prerequisite(*, concept: Concept, prerequisite: Concept) -> bool:
    """Add a direct prerequisite edge after validating graph invariants.

    The relation is directed from a concept to its prerequisite. The operation is
    idempotent for an edge that already exists and returns whether a new edge was
    created.
    """

    if concept.pk == prerequisite.pk:
        raise PrerequisiteGraphError(
            "A concept cannot be its own prerequisite. Choose a different concept."
        )

    if concept.prerequisites.filter(pk=prerequisite.pk).exists():
        return False

    if _has_prerequisite_path(prerequisite, concept):
        raise PrerequisiteGraphError(
            "That link would create a prerequisite cycle. Remove or reroute the "
            "existing dependency before adding it."
        )

    concept.prerequisites.add(prerequisite)
    return True


@transaction.atomic
def remove_prerequisite(*, concept: Concept, prerequisite: Concept) -> bool:
    """Remove a direct prerequisite edge and report whether it existed."""

    existed = concept.prerequisites.filter(pk=prerequisite.pk).exists()
    concept.prerequisites.remove(prerequisite)
    return existed
