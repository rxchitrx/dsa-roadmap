from datetime import date

import pytest
from django.db import IntegrityError

from assessments.models import AssessmentPool, AssessmentSelection
from problems.models import Problem


@pytest.mark.django_db
def test_pool_and_selection_keep_mix_novelty_and_eligibility_metadata(db):
    pool = AssessmentPool.objects.create(
        week_start=date(2026, 8, 31),
        rationale="The pool uses Concepts completed this week.",
        eligibility_metadata={"selection_scope": "current_week_studied_concepts"},
    )
    problem = Problem.objects.create(
        title="Model metadata problem",
        slug="model-metadata-problem",
        statement="Return a value.",
        difficulty=Problem.Difficulty.EASY,
    )
    selection = AssessmentSelection.objects.create(
        pool=pool,
        problem=problem,
        position=1,
        slot_kind=AssessmentSelection.SlotKind.EASY,
        is_unseen=True,
        rationale="Easy slot from a completed Concept.",
        eligibility_metadata={
            "eligible_concepts": [{"id": 1, "name": "Arrays", "topic": "Sequences"}]
        },
    )

    assert pool.selected_count == 1
    assert pool.is_sparse is True
    assert pool.mix_label == "1 easy · 0 medium"
    assert selection.concept_labels == ["Arrays"]


@pytest.mark.django_db
def test_pool_rejects_duplicate_problem_or_position(db):
    pool = AssessmentPool.objects.create(week_start=date(2026, 8, 31))
    problem = Problem.objects.create(
        title="Unique selection problem",
        slug="unique-selection-problem",
        statement="Return a value.",
        difficulty=Problem.Difficulty.MEDIUM,
    )
    data = {
        "pool": pool,
        "problem": problem,
        "position": 1,
        "slot_kind": AssessmentSelection.SlotKind.MEDIUM,
        "rationale": "Selected once.",
    }
    AssessmentSelection.objects.create(**data)

    with pytest.raises(IntegrityError):
        AssessmentSelection.objects.create(**data)
