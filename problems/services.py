from __future__ import annotations

from typing import TypeAlias

from django.core.exceptions import ValidationError
from django.db import transaction

from curriculum.models import Concept

from .models import Problem, ProblemClassification


ClassificationTarget: TypeAlias = Concept | ProblemClassification


def _validate_status(status: str) -> str:
    valid_statuses = {value for value, _label in ProblemClassification.Status.choices}
    if status not in valid_statuses:
        raise ValidationError({"status": f"Unknown classification status: {status}."})
    return status


def _ensure_primary_classification(problem: Problem) -> None:
    """Backfill the relation for a legacy Problem's primary Concept."""

    if not problem.concept_id:
        return

    ProblemClassification.objects.get_or_create(
        problem=problem,
        concept_id=problem.concept_id,
        defaults={"status": ProblemClassification.Status.CONFIRMED},
    )


@transaction.atomic
def add_classification(
    problem: Problem,
    concept: Concept,
    *,
    status: str = ProblemClassification.Status.CONFIRMED,
    note: str = "",
) -> ProblemClassification:
    """Add or revise one Concept tag without changing source metadata."""

    if not isinstance(problem, Problem):
        raise TypeError("problem must be a Problem instance")
    if not isinstance(concept, Concept):
        raise TypeError("concept must be a Concept instance")
    if not problem.pk or not concept.pk:
        raise ValidationError("Save the Problem and Concept before classifying the Problem.")

    status = _validate_status(status)
    note = note.strip()

    # A pre-relation Problem may have been created by the original catalog
    # slice. Preserve its primary concept as a confirmed tag before adding a
    # second tag.
    _ensure_primary_classification(problem)

    candidate = ProblemClassification(
        problem=problem,
        concept=concept,
        status=status,
        note=note,
    )
    candidate.full_clean(validate_unique=False)

    classification, _created = ProblemClassification.objects.update_or_create(
        problem=problem,
        concept=concept,
        defaults={"status": status, "note": note},
    )

    if not problem.concept_id:
        Problem.objects.filter(pk=problem.pk).update(concept_id=concept.pk)
        problem.concept_id = concept.pk

    return classification


@transaction.atomic
def remove_classification(
    problem: Problem,
    target: ClassificationTarget,
) -> bool:
    """Remove one Concept tag and promote a remaining tag when necessary."""

    if not isinstance(problem, Problem):
        raise TypeError("problem must be a Problem instance")
    if not problem.pk:
        return False

    if isinstance(target, ProblemClassification):
        classifications = problem.classifications.filter(pk=target.pk)
        removed_concept_id = target.concept_id
    elif isinstance(target, Concept):
        classifications = problem.classifications.filter(concept=target)
        removed_concept_id = target.pk
    else:
        raise TypeError("target must be a Concept or ProblemClassification instance")

    classification = classifications.first()
    if classification is None:
        return False

    classification.delete()

    if problem.concept_id == removed_concept_id:
        replacement = (
            problem.classifications.filter(status=ProblemClassification.Status.CONFIRMED)
            .select_related("concept")
            .first()
        ) or problem.classifications.select_related("concept").first()
        replacement_concept_id = replacement.concept_id if replacement else None
        Problem.objects.filter(pk=problem.pk).update(concept_id=replacement_concept_id)
        problem.concept_id = replacement_concept_id

    return True


def classification_warning_state(problem: Problem) -> str | None:
    """Expose the warning state for presentation or analytics adapters."""

    return problem.classification_warning_state
