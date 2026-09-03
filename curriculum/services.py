from __future__ import annotations

from django.db import transaction

from .models import Concept


class PrerequisiteGraphError(ValueError):
    """Raised when a requested prerequisite edge is not valid."""


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
