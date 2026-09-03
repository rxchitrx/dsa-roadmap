"""Generate, edit, and persist the learner's next-week plan.

This module intentionally stops at the domain/data boundary.  A view can use
``generate_next_week_plan`` to render a preview, pass the preview through
``edit_next_week_plan`` with the learner's changes, and then call
``save_next_week_plan``.  The preview is pure with respect to planner rows;
only the save operation writes StudyBlocks and their Problem assignments.

The existing planner services remain the source of truth for the individual
selection rules.  This module composes them into one weekly planning flow and
keeps the route integration separate so the plan editor can be added without
changing the existing Today or weekly-plan routes.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from typing import Iterable, Mapping

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from curriculum.models import Concept
from curriculum.services import ConceptRecommendation, recommend_next_concept
from problems.models import Problem
from reviews.services import due_review_queue

from .models import RestDay, StudyBlock, StudyBlockProblem, WorkSession
from .services import (
    SATURDAY_BLOCKS,
    SUNDAY_BLOCKS,
    WEEKDAY_BLOCKS,
    _ordered_problem_candidates,
    _problem_candidates_for_assignment,
    week_start_for,
)


NEXT_WEEK_SUNDAY_REVIEW_COUNT = 5
MAX_PROBLEMS_PER_SOLVE_BLOCK = 2


class NextWeekPlanError(ValidationError):
    """Raised when an editable next-week plan is invalid."""


@dataclass(frozen=True)
class RecommendationPreview:
    """Serializable recommendation evidence for a plan preview."""

    concept_id: int
    concept_name: str
    reason: str
    evidence: tuple[str, ...]

    @classmethod
    def from_recommendation(
        cls,
        recommendation: ConceptRecommendation,
    ) -> "RecommendationPreview":
        return cls(
            concept_id=recommendation.concept.pk,
            concept_name=recommendation.concept.name,
            reason=recommendation.reason,
            evidence=tuple(recommendation.evidence),
        )


@dataclass(frozen=True)
class NextWeekBlock:
    """An editable, unsaved representation of one planned StudyBlock."""

    key: str
    date: date
    title: str
    planned_minutes: int
    position: int
    block_type: str
    source: str = "routine"
    problem_ids: tuple[int, ...] = ()
    problem_assignment_sources: tuple[str, ...] = ()
    concept_id: int | None = None
    carried_from_id: int | None = None
    persisted_id: int | None = None
    status: str = StudyBlock.Status.PENDING

    @property
    def weekday(self) -> int:
        return self.date.weekday()

    @property
    def is_carried_forward(self) -> bool:
        return self.carried_from_id is not None


@dataclass(frozen=True)
class NextWeekPlan:
    """A complete preview or saved representation of one calendar week."""

    week_start: date
    blocks: tuple[NextWeekBlock, ...]
    due_review_ids: tuple[int, ...] = ()
    scheduled_due_review_ids: tuple[int, ...] = ()
    unscheduled_due_review_ids: tuple[int, ...] = ()
    unfinished_block_ids: tuple[int, ...] = ()
    recommendation: RecommendationPreview | None = None
    sunday_review_count: int = NEXT_WEEK_SUNDAY_REVIEW_COUNT
    removed_persisted_ids: tuple[int, ...] = ()

    def __iter__(self):
        return iter(self.blocks)

    def __len__(self) -> int:
        return len(self.blocks)

    @property
    def study_blocks(self) -> tuple[NextWeekBlock, ...]:
        """A descriptive alias for route code that expects planner rows."""

        return self.blocks

    @property
    def total_planned_minutes(self) -> int:
        return sum(block.planned_minutes for block in self.blocks)

    @property
    def block_by_key(self) -> dict[str, NextWeekBlock]:
        return {block.key: block for block in self.blocks}

    @property
    def has_unscheduled_work(self) -> bool:
        return bool(self.unscheduled_due_review_ids)


def next_week_start(reference_date: date | None = None) -> date:
    """Return the Monday after the week containing ``reference_date``."""

    return week_start_for(reference_date or timezone.localdate()) + timedelta(days=7)


def _resolve_target_week(
    reference_date: date | None,
    target_week_start: date | None,
) -> date:
    if target_week_start is not None:
        if not isinstance(target_week_start, date):
            raise NextWeekPlanError("target_week_start must be a date.")
        return week_start_for(target_week_start)
    return next_week_start(reference_date)


def _routine_templates() -> tuple[tuple[int, str, str, int, str], ...]:
    templates: list[tuple[int, str, str, int, str]] = []
    for weekday in range(5):
        for block_type, title, minutes in WEEKDAY_BLOCKS:
            templates.append((weekday, block_type, title, minutes, f"{weekday}-{block_type}"))
    for weekday, blocks in ((5, SATURDAY_BLOCKS), (6, SUNDAY_BLOCKS)):
        for block_type, title, minutes in blocks:
            templates.append((weekday, block_type, title, minutes, f"{weekday}-{block_type}"))
    return tuple(templates)


def _block_assignment_data(block: StudyBlock) -> tuple[tuple[int, ...], tuple[str, ...]]:
    assignments = list(
        block.problem_assignments.order_by("position", "id").values(
            "problem_id", "assignment_source"
        )
    )
    return (
        tuple(item["problem_id"] for item in assignments),
        tuple(item["assignment_source"] for item in assignments),
    )


def _block_type_for(block: StudyBlock) -> str:
    if block.routine_key:
        return block.routine_key.split("-", 1)[-1]
    return "custom"


def _existing_block_draft(block: StudyBlock, *, source: str = "existing") -> NextWeekBlock:
    problem_ids, assignment_sources = _block_assignment_data(block)
    return NextWeekBlock(
        key=block.routine_key or f"persisted-{block.pk}",
        date=block.date,
        title=block.title,
        planned_minutes=block.planned_minutes,
        position=block.position,
        block_type=_block_type_for(block),
        source=source,
        problem_ids=problem_ids,
        problem_assignment_sources=assignment_sources,
        concept_id=block.assigned_concept_id,
        carried_from_id=block.carried_from_id,
        persisted_id=block.pk,
        status=block.status,
    )


def _unfinished_sources(target_week_start: date) -> list[StudyBlock]:
    source_start = target_week_start - timedelta(days=7)
    source_end = target_week_start - timedelta(days=1)
    rest_dates = set(
        RestDay.objects.filter(date__range=(source_start, source_end)).values_list(
            "date", flat=True
        )
    )
    return list(
        StudyBlock.objects.filter(
            date__range=(source_start, source_end),
            status=StudyBlock.Status.PENDING,
        )
        .exclude(date__in=rest_dates)
        .order_by("date", "position", "id")
    )


def _carry_forward_draft(
    source: StudyBlock,
    *,
    target_week_start: date,
    position: int,
) -> NextWeekBlock:
    problem_ids, assignment_sources = _block_assignment_data(source)
    return NextWeekBlock(
        key=f"carry-forward-{source.pk}",
        date=target_week_start,
        title=source.title,
        planned_minutes=source.planned_minutes,
        position=position,
        block_type="unfinished",
        source="unfinished",
        problem_ids=problem_ids,
        problem_assignment_sources=assignment_sources,
        concept_id=source.assigned_concept_id,
        carried_from_id=source.pk,
        status=StudyBlock.Status.PENDING,
    )


def _due_reviews(now: datetime) -> list[int]:
    return list(due_review_queue(now=now).values_list("problem_id", flat=True))


def _copy_with_problems(
    block: NextWeekBlock,
    problem_ids: Iterable[int],
    *,
    source: str | None = None,
    assignment_source: str = StudyBlockProblem.AssignmentSource.AUTOMATIC,
) -> NextWeekBlock:
    ids = tuple(dict.fromkeys(int(problem_id) for problem_id in problem_ids))
    return replace(
        block,
        problem_ids=ids,
        problem_assignment_sources=tuple(assignment_source for _ in ids),
        source=source or block.source,
    )


def _insert_or_replace_block(
    blocks: list[NextWeekBlock],
    replacement: NextWeekBlock,
) -> None:
    for index, block in enumerate(blocks):
        if block.key == replacement.key:
            blocks[index] = replacement
            return
    blocks.append(replacement)


def _assign_due_reviews(
    blocks: list[NextWeekBlock],
    due_review_ids: tuple[int, ...],
    *,
    sunday_review_count: int,
) -> tuple[list[NextWeekBlock], tuple[int, ...]]:
    """Place each due Problem once, prioritizing weekday review blocks."""

    assigned_problem_ids = {
        problem_id for block in blocks for problem_id in block.problem_ids
    }
    scheduled: list[int] = [
        problem_id for problem_id in due_review_ids if problem_id in assigned_problem_ids
    ]
    remaining = [
        problem_id
        for problem_id in due_review_ids
        if problem_id not in assigned_problem_ids
    ]

    review_blocks = sorted(
        (
            block
            for block in blocks
            if block.block_type == "review" and block.weekday < 5
        ),
        key=lambda block: (block.date, block.position, block.key),
    )
    for block in review_blocks:
        if block.problem_ids or not remaining:
            continue
        problem_id = remaining.pop(0)
        replacement = _copy_with_problems(
            block,
            (problem_id,),
            source="due_review",
        )
        _insert_or_replace_block(blocks, replacement)
        scheduled.append(problem_id)

    sunday_blocks = sorted(
        (block for block in blocks if block.block_type == "review-batch"),
        key=lambda block: (block.date, block.position, block.key),
    )
    if sunday_blocks:
        block = sunday_blocks[0]
        existing = list(block.problem_ids)
        available = max(0, sunday_review_count - len(existing))
        additions = remaining[:available]
        if additions:
            replacement = _copy_with_problems(
                block,
                existing + additions,
                source="sunday_review_batch",
            )
            _insert_or_replace_block(blocks, replacement)
            scheduled.extend(additions)
            remaining = remaining[len(additions) :]

    return blocks, tuple(scheduled)


def _assign_recommended_concept(
    blocks: list[NextWeekBlock],
    recommendation: RecommendationPreview | None,
) -> list[NextWeekBlock]:
    if recommendation is None:
        return blocks
    concept_blocks = sorted(
        (block for block in blocks if block.block_type == "concept"),
        key=lambda block: (block.date, block.position, block.key),
    )
    if not concept_blocks:
        return blocks
    if any(block.concept_id is not None for block in concept_blocks):
        return blocks
    _insert_or_replace_block(
        blocks,
        replace(concept_blocks[0], concept_id=recommendation.concept_id, source="concept_recommendation"),
    )
    return blocks


def _assign_weekday_problems(
    blocks: list[NextWeekBlock],
    *,
    now: datetime,
) -> list[NextWeekBlock]:
    """Preview the existing weekday assignment policy without writing rows."""

    candidates = _ordered_problem_candidates(
        _problem_candidates_for_assignment(),
        now=now,
    )
    claimed = {
        problem_id for block in blocks for problem_id in block.problem_ids
    }
    solve_blocks = sorted(
        (
            block
            for block in blocks
            if block.block_type == "problems" and block.weekday < 5
            and block.status == StudyBlock.Status.PENDING
        ),
        key=lambda block: (block.date, block.position, block.key),
    )
    for block in solve_blocks:
        if len(block.problem_ids) >= MAX_PROBLEMS_PER_SOLVE_BLOCK:
            continue
        selected = list(block.problem_ids)
        for problem in candidates:
            if len(selected) >= MAX_PROBLEMS_PER_SOLVE_BLOCK:
                break
            if problem.pk in claimed:
                continue
            selected.append(problem.pk)
            claimed.add(problem.pk)
        if tuple(selected) != block.problem_ids:
            _insert_or_replace_block(
                blocks,
                _copy_with_problems(block, selected, source="weekday_problem_assignment"),
            )
    return blocks


def _normalize_blocks(blocks: Iterable[NextWeekBlock]) -> tuple[NextWeekBlock, ...]:
    ordered = sorted(blocks, key=lambda block: (block.date, block.position, block.key))
    positions_by_date: dict[date, int] = {}
    normalized = []
    for block in ordered:
        position = positions_by_date.get(block.date, 0)
        positions_by_date[block.date] = position + 1
        normalized.append(replace(block, position=position))
    return tuple(normalized)


def generate_next_week_plan(
    reference_date: date | None = None,
    *,
    target_week_start: date | None = None,
    now: datetime | None = None,
    sunday_review_count: int = NEXT_WEEK_SUNDAY_REVIEW_COUNT,
) -> NextWeekPlan:
    """Build an editable next-week preview without changing planner rows.

    ``target_week_start`` is useful for deterministic callers and tests.  When
    omitted, the target is the Monday immediately after the current calendar
    week.  Existing target-week rows are loaded into the preview so repeated
    generation preserves manual edits and completion state.
    """

    if (
        not isinstance(sunday_review_count, int)
        or isinstance(sunday_review_count, bool)
        or sunday_review_count < 1
    ):
        raise NextWeekPlanError("sunday_review_count must be at least one.")

    target_start = _resolve_target_week(reference_date, target_week_start)
    current_time = now or timezone.now()
    due_review_ids = tuple(_due_reviews(current_time))

    existing = {
        block.routine_key: block
        for block in StudyBlock.objects.filter(week_start=target_start)
        if block.routine_key
    }
    blocks: list[NextWeekBlock] = []
    positions_by_date: dict[date, int] = {}
    for weekday, block_type, title, minutes, key in _routine_templates():
        block_date = target_start + timedelta(days=weekday)
        position = positions_by_date.get(block_date, 0)
        positions_by_date[block_date] = position + 1
        persisted = existing.get(key)
        if persisted is not None:
            blocks.append(_existing_block_draft(persisted))
            continue
        blocks.append(
            NextWeekBlock(
                key=key,
                date=target_start + timedelta(days=weekday),
                title=title,
                planned_minutes=minutes,
                position=position,
                block_type=block_type,
            )
        )

    # Preserve custom or previously carried rows already in the target week.
    known_keys = {block.key for block in blocks}
    for persisted in StudyBlock.objects.filter(week_start=target_start).order_by(
        "date", "position", "id"
    ):
        key = persisted.routine_key or f"persisted-{persisted.pk}"
        if key not in known_keys:
            blocks.append(_existing_block_draft(persisted))
            known_keys.add(key)

    unfinished_sources = _unfinished_sources(target_start)
    existing_carried_from = {
        block.carried_from_id
        for block in blocks
        if block.carried_from_id is not None
    }
    monday_position = max(
        (block.position for block in blocks if block.date == target_start),
        default=-1,
    ) + 1
    unfinished_ids: list[int] = []
    for source in unfinished_sources:
        if source.pk in existing_carried_from:
            unfinished_ids.append(source.pk)
            continue
        blocks.append(
            _carry_forward_draft(
                source,
                target_week_start=target_start,
                position=monday_position,
            )
        )
        monday_position += 1
        unfinished_ids.append(source.pk)

    recommendation_model = recommend_next_concept(now=current_time)
    recommendation = (
        RecommendationPreview.from_recommendation(recommendation_model)
        if recommendation_model is not None
        else None
    )
    blocks = _assign_recommended_concept(blocks, recommendation)
    blocks, scheduled_due_review_ids = _assign_due_reviews(
        blocks,
        due_review_ids,
        sunday_review_count=sunday_review_count,
    )
    blocks = _assign_weekday_problems(blocks, now=current_time)
    blocks = list(_normalize_blocks(blocks))

    scheduled_set = set(scheduled_due_review_ids)
    # A due Problem already carried forward or already present in a manually
    # edited target block is still scheduled work, even if it needed no new row.
    scheduled_set.update(
        problem_id
        for problem_id in due_review_ids
        if any(problem_id in block.problem_ids for block in blocks)
    )
    scheduled_due_review_ids = tuple(
        problem_id for problem_id in due_review_ids if problem_id in scheduled_set
    )
    unscheduled_due_review_ids = tuple(
        problem_id for problem_id in due_review_ids if problem_id not in scheduled_set
    )

    return NextWeekPlan(
        week_start=target_start,
        blocks=tuple(blocks),
        due_review_ids=due_review_ids,
        scheduled_due_review_ids=scheduled_due_review_ids,
        unscheduled_due_review_ids=unscheduled_due_review_ids,
        unfinished_block_ids=tuple(unfinished_ids),
        recommendation=recommendation,
        sunday_review_count=sunday_review_count,
    )


def _coerce_problem_ids(value) -> tuple[int, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)):
        value = [value]
    try:
        values = tuple(value)
    except TypeError as error:
        raise NextWeekPlanError("problem_ids must be an iterable of Problems or ids.") from error

    ids: list[int] = []
    for item in values:
        problem_id = item.pk if isinstance(item, Problem) else item
        try:
            problem_id = int(problem_id)
        except (TypeError, ValueError) as error:
            raise NextWeekPlanError("Each Problem assignment must have a valid id.") from error
        if problem_id < 1:
            raise NextWeekPlanError("Each Problem assignment must have a valid id.")
        if problem_id not in ids:
            ids.append(problem_id)
    return tuple(ids)


def _validate_problem_ids(
    problem_ids: tuple[int, ...],
    *,
    block_type: str,
) -> None:
    if block_type == "problems" and len(problem_ids) > MAX_PROBLEMS_PER_SOLVE_BLOCK:
        raise NextWeekPlanError("A solve block can contain at most two Problems.")
    active_ids = set(
        Problem.objects.filter(pk__in=problem_ids, is_active=True).values_list(
            "pk", flat=True
        )
    )
    if active_ids != set(problem_ids):
        raise NextWeekPlanError("Manual assignments must use active catalog Problems.")


def _validate_plan_blocks(plan: NextWeekPlan) -> None:
    """Validate a plan even when a caller constructed it without edit helpers."""

    if plan.week_start != week_start_for(plan.week_start):
        raise NextWeekPlanError("A plan must start on a Monday.")
    if (
        not isinstance(plan.sunday_review_count, int)
        or isinstance(plan.sunday_review_count, bool)
        or plan.sunday_review_count < 1
    ):
        raise NextWeekPlanError("sunday_review_count must be at least one.")

    seen_problem_ids: dict[int, str] = {}
    seen_keys: set[str] = set()
    for block in plan.blocks:
        if not block.key or block.key in seen_keys:
            raise NextWeekPlanError("Every next-week block must have a unique key.")
        seen_keys.add(block.key)
        if not isinstance(block.title, str) or not block.title.strip():
            raise NextWeekPlanError("A study block title cannot be empty.")
        if not isinstance(block.planned_minutes, int) or isinstance(
            block.planned_minutes, bool
        ) or block.planned_minutes < 1:
            raise NextWeekPlanError("planned_minutes must be a positive integer.")
        if not isinstance(block.date, date) or not (
            plan.week_start <= block.date <= plan.week_start + timedelta(days=6)
        ):
            raise NextWeekPlanError("A block must remain inside the planned week.")
        _validate_problem_ids(block.problem_ids, block_type=block.block_type)
        if block.problem_assignment_sources and len(
            block.problem_assignment_sources
        ) != len(block.problem_ids):
            raise NextWeekPlanError(
                "Problem assignment sources must match the assigned Problems."
            )
        if block.concept_id is not None and not Concept.objects.filter(
            pk=block.concept_id
        ).exists():
            raise NextWeekPlanError("assigned_concept must refer to an existing Concept.")
        for problem_id in block.problem_ids:
            previous_key = seen_problem_ids.get(problem_id)
            if previous_key is not None and previous_key != block.key:
                raise NextWeekPlanError(
                    f"Problem {problem_id} is assigned more than once in the plan."
                )
            seen_problem_ids[problem_id] = block.key


def _coerce_concept_id(value) -> int | None:
    if value is None or value == "":
        return None
    concept_id = value.pk if isinstance(value, Concept) else value
    try:
        concept_id = int(concept_id)
    except (TypeError, ValueError) as error:
        raise NextWeekPlanError("assigned_concept must be a valid Concept id.") from error
    if not Concept.objects.filter(pk=concept_id).exists():
        raise NextWeekPlanError("assigned_concept must refer to an existing Concept.")
    return concept_id


def edit_next_week_plan(
    plan: NextWeekPlan,
    edits: Mapping[str, Mapping[str, object]] | None = None,
) -> NextWeekPlan:
    """Return a validated edited copy of ``plan`` without persisting it.

    Supported fields are ``title``, ``planned_minutes``, ``date``,
    ``position``, ``problem_ids``, ``assigned_concept``/``concept_id``, and
    ``remove``.  A view can use the stable block keys as form field prefixes.
    """

    if not isinstance(plan, NextWeekPlan):
        raise TypeError("plan must be a NextWeekPlan.")
    if edits is None:
        _validate_plan_blocks(plan)
        return plan
    if not isinstance(edits, Mapping):
        raise NextWeekPlanError("edits must map block keys to field changes.")

    blocks = list(plan.blocks)
    by_key = {block.key: index for index, block in enumerate(blocks)}
    allowed_fields = {
        "title",
        "planned_minutes",
        "date",
        "position",
        "problem_ids",
        "assigned_problems",
        "assigned_concept",
        "concept_id",
        "remove",
    }
    for key, changes in edits.items():
        if key not in by_key:
            raise NextWeekPlanError(f"Unknown next-week block key: {key}.")
        if not isinstance(changes, Mapping):
            raise NextWeekPlanError(f"Edits for {key} must be a mapping.")
        unknown = set(changes) - allowed_fields
        if unknown:
            names = ", ".join(sorted(unknown))
            raise NextWeekPlanError(f"Unsupported edit field(s) for {key}: {names}.")

        index = by_key[key]
        block = blocks[index]
        if changes.get("remove"):
            if block.persisted_id is not None and (
                block.status == StudyBlock.Status.COMPLETED
                or WorkSession.objects.filter(study_block_id=block.persisted_id).exists()
            ):
                raise NextWeekPlanError(
                    "A saved block with completion or timer history cannot be removed."
                )
            blocks.pop(index)
            by_key = {item.key: position for position, item in enumerate(blocks)}
            continue

        updates = {}
        if "title" in changes:
            title = changes["title"]
            if not isinstance(title, str) or not title.strip():
                raise NextWeekPlanError("A study block title cannot be empty.")
            updates["title"] = title.strip()
        if "planned_minutes" in changes:
            minutes = changes["planned_minutes"]
            if isinstance(minutes, bool):
                raise NextWeekPlanError("planned_minutes must be a positive integer.")
            try:
                minutes = int(minutes)
            except (TypeError, ValueError) as error:
                raise NextWeekPlanError("planned_minutes must be a positive integer.") from error
            if minutes < 1:
                raise NextWeekPlanError("planned_minutes must be a positive integer.")
            updates["planned_minutes"] = minutes
        if "date" in changes:
            edited_date = changes["date"]
            if not isinstance(edited_date, date):
                raise NextWeekPlanError("date edits must use a date value.")
            if not plan.week_start <= edited_date <= plan.week_start + timedelta(days=6):
                raise NextWeekPlanError("A block must remain inside the planned week.")
            updates["date"] = edited_date
        if "position" in changes:
            position = changes["position"]
            if isinstance(position, bool):
                raise NextWeekPlanError("position must be zero or a positive integer.")
            try:
                position = int(position)
            except (TypeError, ValueError) as error:
                raise NextWeekPlanError("position must be zero or a positive integer.") from error
            if position < 0:
                raise NextWeekPlanError("position must be zero or a positive integer.")
            updates["position"] = position
        if "problem_ids" in changes or "assigned_problems" in changes:
            field_name = "problem_ids" if "problem_ids" in changes else "assigned_problems"
            problem_ids = _coerce_problem_ids(changes[field_name])
            _validate_problem_ids(problem_ids, block_type=block.block_type)
            updates["problem_ids"] = problem_ids
            updates["problem_assignment_sources"] = tuple(
                StudyBlockProblem.AssignmentSource.MANUAL for _ in problem_ids
            )
        if "assigned_concept" in changes or "concept_id" in changes:
            field_name = "assigned_concept" if "assigned_concept" in changes else "concept_id"
            updates["concept_id"] = _coerce_concept_id(changes[field_name])
            updates["source"] = "manual"

        blocks[index] = replace(block, **updates)

    edited_plan = replace(plan, blocks=_normalize_blocks(blocks))
    removed_ids = list(plan.removed_persisted_ids)
    for key, changes in edits.items():
        if changes.get("remove"):
            removed_block = next(
                (block for block in plan.blocks if block.key == key),
                None,
            )
            if removed_block and removed_block.persisted_id is not None:
                removed_ids.append(removed_block.persisted_id)
    edited_plan = replace(
        edited_plan,
        removed_persisted_ids=tuple(dict.fromkeys(removed_ids)),
    )
    _validate_plan_blocks(edited_plan)
    return edited_plan


def edit_next_week_block(
    plan: NextWeekPlan,
    block_key: str,
    **changes,
) -> NextWeekPlan:
    """Convenience wrapper for editing one block."""

    return edit_next_week_plan(plan, {block_key: changes})


def _save_assignments(block: StudyBlock, draft: NextWeekBlock) -> None:
    desired_ids = tuple(dict.fromkeys(draft.problem_ids))
    current = {
        assignment.problem_id: assignment
        for assignment in StudyBlockProblem.objects.select_for_update().filter(
            study_block=block
        )
    }
    desired_set = set(desired_ids)
    for problem_id, assignment in current.items():
        if problem_id not in desired_set:
            assignment.delete()

    # Move existing rows out of the way so a reordered assignment cannot
    # transiently violate the unique (block, position) constraint.
    retained = [current[problem_id] for problem_id in desired_ids if problem_id in current]
    for offset, assignment in enumerate(retained, start=1000):
        if assignment.position != offset:
            assignment.position = offset
            assignment.save(update_fields=("position", "updated_at"))

    source_by_problem = dict(zip(desired_ids, draft.problem_assignment_sources))
    default_source = (
        StudyBlockProblem.AssignmentSource.MANUAL
        if draft.source in {"manual", "existing"}
        else StudyBlockProblem.AssignmentSource.AUTOMATIC
    )
    for position, problem_id in enumerate(desired_ids):
        assignment_source = source_by_problem.get(problem_id, default_source)
        if problem_id in current:
            assignment = current[problem_id]
            assignment.position = position
            assignment.assignment_source = assignment_source
            assignment.save(update_fields=("position", "assignment_source", "updated_at"))
        else:
            StudyBlockProblem.objects.create(
                study_block=block,
                problem_id=problem_id,
                position=position,
                assignment_source=assignment_source,
            )


@transaction.atomic
def save_next_week_plan(
    plan: NextWeekPlan,
    edits: Mapping[str, Mapping[str, object]] | None = None,
) -> NextWeekPlan:
    """Persist an edited plan, preserving completion and timer history.

    Routine and carry-forward keys make repeated saves idempotent.  Existing
    rows are updated in place, so a completed block is never reset to pending
    and its WorkSession history remains attached.
    """

    if not isinstance(plan, NextWeekPlan):
        raise TypeError("plan must be a NextWeekPlan.")
    if edits is not None:
        plan = edit_next_week_plan(plan, edits)
    # Re-run the edit invariants for callers that constructed a dataclass by
    # hand rather than using edit_next_week_plan.
    plan = edit_next_week_plan(plan)

    for persisted_id in plan.removed_persisted_ids:
        block = StudyBlock.objects.select_for_update().filter(
            pk=persisted_id,
            week_start=plan.week_start,
        ).first()
        if block is None:
            continue
        if block.status == StudyBlock.Status.COMPLETED or WorkSession.objects.filter(
            study_block=block
        ).exists():
            raise NextWeekPlanError(
                "A saved block with completion or timer history cannot be removed."
            )
        block.delete()

    existing_by_key = {
        block.routine_key: block
        for block in StudyBlock.objects.select_for_update().filter(
            week_start=plan.week_start,
            routine_key__isnull=False,
        )
    }
    persisted_blocks: list[NextWeekBlock] = []
    for draft in plan.blocks:
        block = None
        if draft.persisted_id is not None:
            block = StudyBlock.objects.select_for_update().filter(
                pk=draft.persisted_id,
                week_start=plan.week_start,
            ).first()
        if block is None:
            block = existing_by_key.get(draft.key)

        if block is None:
            carried_from = None
            if draft.carried_from_id is not None:
                carried_from = StudyBlock.objects.filter(pk=draft.carried_from_id).first()
                if carried_from is None:
                    raise NextWeekPlanError(
                        f"Unfinished source {draft.carried_from_id} no longer exists."
                    )
            block = StudyBlock.objects.create(
                date=draft.date,
                week_start=plan.week_start,
                routine_key=draft.key,
                title=draft.title,
                planned_minutes=draft.planned_minutes,
                assigned_concept_id=draft.concept_id,
                concept_assignment_source=(
                    StudyBlock.ConceptAssignmentSource.MANUAL
                    if draft.source == "manual"
                    else StudyBlock.ConceptAssignmentSource.AUTOMATIC
                ),
                carried_from=carried_from,
                position=draft.position,
                status=StudyBlock.Status.PENDING,
            )
            existing_by_key[draft.key] = block
        else:
            block.date = draft.date
            block.title = draft.title
            block.planned_minutes = draft.planned_minutes
            block.position = draft.position
            if draft.concept_id != block.assigned_concept_id:
                block.assigned_concept_id = draft.concept_id
                block.concept_assignment_source = (
                    StudyBlock.ConceptAssignmentSource.MANUAL
                    if draft.source == "manual"
                    else StudyBlock.ConceptAssignmentSource.AUTOMATIC
                )
            block.save(
                update_fields=(
                    "date",
                    "title",
                    "planned_minutes",
                    "position",
                    "assigned_concept",
                    "concept_assignment_source",
                    "updated_at",
                )
            )

        _save_assignments(block, draft)
        persisted_blocks.append(_existing_block_draft(block, source=draft.source))

    saved_blocks = _normalize_blocks(persisted_blocks)
    return replace(plan, blocks=saved_blocks)


def generate_and_save_next_week_plan(
    reference_date: date | None = None,
    *,
    target_week_start: date | None = None,
    now: datetime | None = None,
    sunday_review_count: int = NEXT_WEEK_SUNDAY_REVIEW_COUNT,
    edits: Mapping[str, Mapping[str, object]] | None = None,
) -> NextWeekPlan:
    """Generate a preview, apply optional edits, and save it in one call."""

    plan = generate_next_week_plan(
        reference_date,
        target_week_start=target_week_start,
        now=now,
        sunday_review_count=sunday_review_count,
    )
    if edits:
        plan = edit_next_week_plan(plan, edits)
    return save_next_week_plan(plan)
