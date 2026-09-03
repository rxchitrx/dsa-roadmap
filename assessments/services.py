from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from curriculum.models import Concept
from planner.models import StudyBlock
from practice.models import LearningStatus, ProblemLearningStatus
from problems.models import Problem

from .models import AssessmentPool, AssessmentSelection


SLOT_PLAN = (
    (AssessmentSelection.SlotKind.EASY, 1),
    (AssessmentSelection.SlotKind.MEDIUM, 2),
)


def week_start_for(value: date) -> date:
    """Return the Monday containing ``value`` without changing planner code."""

    return value - timedelta(days=value.weekday())


def _week_end_for(week_start: date) -> date:
    return week_start + timedelta(days=6)


def _is_concept_study_block(block: StudyBlock) -> bool:
    """Recognize the planner's concept-learning block without changing it."""

    if block.routine_key:
        return block.routine_key.endswith("-concept")
    return "concept" in block.title.casefold()


def get_studied_concept_evidence(
    week_start: date | None = None,
) -> dict[int, dict]:
    """Return explicit current-week Concept study evidence keyed by Concept id.

    A completed concept-learning StudyBlock is the intentionally narrow signal
    for this slice. A partially timed block is not silently treated as studied;
    later assessment work can decide how partial evidence should count.
    """

    start = week_start_for(week_start or timezone.localdate())
    blocks = (
        StudyBlock.objects.select_related("assigned_concept__topic")
        .filter(
            date__range=(start, _week_end_for(start)),
            assigned_concept__isnull=False,
            status=StudyBlock.Status.COMPLETED,
        )
        .order_by("date", "position", "id")
    )

    evidence_by_concept: dict[int, dict] = {}
    for block in blocks:
        if not _is_concept_study_block(block):
            continue

        concept = block.assigned_concept
        evidence = evidence_by_concept.setdefault(
            concept.pk,
            {
                "concept": concept,
                "evidence": [],
            },
        )
        evidence["evidence"].append(
            {
                "type": "completed_study_block",
                "block_id": block.pk,
                "date": block.date.isoformat(),
                "title": block.title,
            }
        )

    return evidence_by_concept


def get_studied_concepts(week_start: date | None = None) -> list[Concept]:
    """Return Concepts with explicit completed study evidence this week."""

    evidence = get_studied_concept_evidence(week_start)
    return [item["concept"] for item in evidence.values()]


def _problem_concept_metadata(problem: Problem, studied_evidence: dict[int, dict]) -> list[dict]:
    """Explain which studied Concepts make a Problem eligible."""

    concept_ids = set()
    if problem.concept_id:
        concept_ids.add(problem.concept_id)
    concept_ids.update(
        classification.concept_id
        for classification in problem.classifications.all()
    )

    matching = []
    for concept_id in sorted(concept_ids):
        if concept_id not in studied_evidence:
            continue
        concept = studied_evidence[concept_id]["concept"]
        matching.append(
            {
                "id": concept.pk,
                "name": concept.name,
                "topic": concept.topic.name,
                "evidence": studied_evidence[concept_id]["evidence"],
            }
        )
    return matching


def _unseen_by_problem_id(problem_ids: list[int]) -> dict[int, bool]:
    statuses = dict(
        ProblemLearningStatus.objects.filter(problem_id__in=problem_ids).values_list(
            "problem_id", "status"
        )
    )
    return {
        problem_id: statuses.get(problem_id, LearningStatus.UNSEEN)
        == LearningStatus.UNSEEN
        for problem_id in problem_ids
    }


def _candidate_pool(studied_evidence: dict[int, dict]) -> list[dict]:
    if not studied_evidence:
        return []

    studied_ids = list(studied_evidence)
    candidates = list(
        Problem.objects.filter(
            Q(concept_id__in=studied_ids)
            | Q(classifications__concept_id__in=studied_ids),
            difficulty__in=(
                Problem.Difficulty.EASY,
                Problem.Difficulty.MEDIUM,
            ),
            is_active=True,
        )
        .select_related("concept__topic")
        .prefetch_related(
            "classifications__concept__topic",
        )
        .distinct()
    )
    unseen_by_problem_id = _unseen_by_problem_id([item.pk for item in candidates])

    candidate_rows = []
    for problem in candidates:
        eligible_concepts = _problem_concept_metadata(problem, studied_evidence)
        if not eligible_concepts:
            continue
        candidate_rows.append(
            {
                "problem": problem,
                "difficulty": problem.difficulty,
                "is_unseen": unseen_by_problem_id[problem.pk],
                "eligible_concepts": eligible_concepts,
            }
        )
    return candidate_rows


def _candidate_sort_key(row: dict) -> tuple:
    problem = row["problem"]
    return (
        not row["is_unseen"],
        problem.display_order,
        problem.title.casefold(),
        problem.pk,
    )


def _selection_rationale(row: dict, slot_kind: str) -> str:
    concept_names = ", ".join(
        concept["name"] for concept in row["eligible_concepts"]
    )
    novelty = "unseen preference" if row["is_unseen"] else "no unseen eligible Problem remained"
    return (
        f"{slot_kind.title()} slot from current-week studied Concept(s): "
        f"{concept_names}. Chosen with {novelty}."
    )


def _pool_rationale(
    studied_evidence: dict[int, dict],
    candidate_rows: list[dict],
    selected_rows: list[tuple[str, dict]],
) -> str:
    concept_names = ", ".join(
        item["concept"].name for item in studied_evidence.values()
    )
    candidate_counts = Counter(row["difficulty"] for row in candidate_rows)
    selected_counts = Counter(kind for kind, _row in selected_rows)
    selected_unseen = sum(row["is_unseen"] for _kind, row in selected_rows)
    selected_count = len(selected_rows)
    rationale = (
        f"Eligible Concepts studied this week: {concept_names or 'none'}. "
        f"The selector requested 1 easy and 2 medium Problems, preferring unseen "
        f"Problems within each difficulty. Found {candidate_counts['easy']} easy and "
        f"{candidate_counts['medium']} medium candidates; selected "
        f"{selected_counts['easy']} easy and {selected_counts['medium']} medium "
        f"({selected_unseen} of {selected_count} unseen)."
    )
    if selected_count < 3:
        rationale += " The current-week pool is sparse, so no older-Concept fallback was added in this slice."
    return rationale


@transaction.atomic
def generate_saturday_assessment_pool(
    week_start: date | None = None,
) -> AssessmentPool:
    """Generate the current-week Saturday pool with a fixed difficulty mix.

    This slice deliberately selects only from Concepts with completed
    current-week study evidence. It never pads the pool with older Concepts;
    issue #26 owns fallback selection and separate fallback scoring.
    """

    start = week_start_for(week_start or timezone.localdate())
    studied_evidence = get_studied_concept_evidence(start)
    candidate_rows = _candidate_pool(studied_evidence)
    selected_rows: list[tuple[str, dict]] = []
    selected_problem_ids: set[int] = set()

    for slot_kind, requested_count in SLOT_PLAN:
        matching = sorted(
            (
                row
                for row in candidate_rows
                if row["difficulty"] == slot_kind
                and row["problem"].pk not in selected_problem_ids
            ),
            key=_candidate_sort_key,
        )
        for row in matching[:requested_count]:
            selected_rows.append((slot_kind, row))
            selected_problem_ids.add(row["problem"].pk)

    pool, _created = AssessmentPool.objects.get_or_create(
        week_start=start,
        defaults={
            "requested_problem_count": 3,
            "duration_minutes": 90,
        },
    )
    pool.selections.all().delete()

    candidate_counts = Counter(row["difficulty"] for row in candidate_rows)
    unseen_candidate_counts = Counter(
        row["difficulty"] for row in candidate_rows if row["is_unseen"]
    )
    metadata = {
        "week_start": start.isoformat(),
        "studied_concepts": [
            {
                "id": item["concept"].pk,
                "name": item["concept"].name,
                "topic": item["concept"].topic.name,
                "evidence": item["evidence"],
            }
            for item in studied_evidence.values()
        ],
        "requested_mix": {"easy": 1, "medium": 2},
        "candidate_counts": {
            "easy": candidate_counts["easy"],
            "medium": candidate_counts["medium"],
        },
        "unseen_candidate_counts": {
            "easy": unseen_candidate_counts["easy"],
            "medium": unseen_candidate_counts["medium"],
        },
        "selected_counts": dict(Counter(kind for kind, _row in selected_rows)),
        "selection_scope": "current_week_studied_concepts",
        "fallback_included": False,
    }
    pool.rationale = _pool_rationale(studied_evidence, candidate_rows, selected_rows)
    pool.eligibility_metadata = metadata
    pool.save(update_fields=("rationale", "eligibility_metadata", "updated_at"))

    for position, (slot_kind, row) in enumerate(selected_rows, start=1):
        problem = row["problem"]
        AssessmentSelection.objects.create(
            pool=pool,
            problem=problem,
            position=position,
            slot_kind=slot_kind,
            is_unseen=row["is_unseen"],
            rationale=_selection_rationale(row, slot_kind),
            eligibility_metadata={
                "eligibility": "current_week_studied_concept",
                "eligible_concepts": row["eligible_concepts"],
                "difficulty": problem.difficulty,
                "is_unseen": row["is_unseen"],
            },
        )

    return pool


# A descriptive alias for callers that care about the selection operation.
select_saturday_problems = generate_saturday_assessment_pool
