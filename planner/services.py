from datetime import date, timedelta

from django.db import IntegrityError, transaction
from django.db.models import Max, Q
from django.utils import timezone

from curriculum.models import Concept
from curriculum.services import recommend_next_concept
from practice.models import LearningStatus, ProblemLearningStatus
from problems.models import Problem, ProblemClassification
from progress.models import ConceptCheckpoint
from reviews.models import ProblemReview

from .models import RestDay, StudyBlock, StudyBlockProblem, WorkSession


class WorkSessionTransitionError(Exception):
    """Base error for an invalid timer action."""


class ActiveWorkSessionError(WorkSessionTransitionError):
    """Raised when a block already has a running or paused timer."""


class InvalidWorkSessionStateError(WorkSessionTransitionError):
    """Raised when a timer action does not match the session state."""


# Each tuple is a stable key, learner-facing title, and planned duration.
WEEKDAY_BLOCKS = (
    ("review", "Re-solve an old question", 20),
    ("concept", "Learn one concept", 30),
    ("problems", "Solve one or two problems", 50),
    ("rewrite", "Study/rewrite the solution", 20),
    ("project", "Project or Python implementation", 30),
    ("cs-subject", "DBMS/OS/CN/OOP", 30),
)

SATURDAY_BLOCKS = (
    ("assessment", "Timed assessment", 90),
    ("mistake-analysis", "Analyse every assessment mistake", 30),
    ("project", "Project work", 120),
)

SUNDAY_BLOCKS = (
    ("review-batch", "Re-solve five older questions", 100),
    ("cs-revision", "Revise one CS subject", 30),
    ("project", "Work on the project", 120),
    ("planning", "Plan the next week", 30),
)


def week_start_for(value: date) -> date:
    """Return the Monday belonging to the calendar week for ``value``."""

    return value - timedelta(days=value.weekday())


def _templates_for_week() -> tuple[tuple[int, tuple[tuple[str, str, int], ...]], ...]:
    return (
        *((weekday, WEEKDAY_BLOCKS) for weekday in range(5)),
        (5, SATURDAY_BLOCKS),
        (6, SUNDAY_BLOCKS),
    )


DEFAULT_WEEKLY_ROUTINE_BLOCK_COUNT = sum(
    len(blocks) for _, blocks in _templates_for_week()
)


def is_rest_day(value: date) -> bool:
    return RestDay.objects.filter(date=value).exists()


@transaction.atomic
def toggle_rest_day(value: date) -> bool:
    """Toggle a rest day while leaving every StudyBlock untouched."""

    rest_day, created = RestDay.objects.get_or_create(date=value)
    if not created:
        rest_day.delete()
    return created


def _carry_forward_position(week_start: date) -> int:
    last_position = (
        StudyBlock.objects.filter(
            week_start=week_start,
            carried_from__isnull=True,
        ).aggregate(last_position=Max("position"))["last_position"]
    )
    return (last_position + 1) if last_position is not None else 0


def _normalize_carry_forward_positions(week_start: date) -> None:
    """Keep copied work after the editable routine when a week is generated."""

    next_position = _carry_forward_position(week_start)
    carry_forward_blocks = StudyBlock.objects.filter(
        week_start=week_start,
        carried_from__isnull=False,
    ).order_by("created_at", "id")
    for block in carry_forward_blocks:
        if block.position != next_position:
            block.position = next_position
            block.save(update_fields=("position", "updated_at"))
        next_position += 1


@transaction.atomic
def carry_forward_unfinished_blocks(
    target_week_start: date | None = None,
) -> list[StudyBlock]:
    """Copy unfinished work from the prior week into the target week.

    Copies are new StudyBlocks linked to their source. The source row and all
    of its WorkSession history remain unchanged. The operation is idempotent
    through the generated routine key, so refreshing a planning view cannot
    create duplicate carry-forward work.
    """

    target_start = week_start_for(target_week_start or timezone.localdate())
    target_date = target_start
    if is_rest_day(target_date):
        return []

    source_start = target_start - timedelta(days=7)
    source_end = target_start - timedelta(days=1)
    source_rest_dates = set(
        RestDay.objects.filter(date__range=(source_start, source_end)).values_list(
            "date", flat=True
        )
    )
    source_blocks = list(
        StudyBlock.objects.select_for_update()
        .filter(
            date__range=(source_start, source_end),
            status=StudyBlock.Status.PENDING,
        )
        .order_by("date", "position", "id")
    )
    source_blocks = [
        block for block in source_blocks if block.date not in source_rest_dates
    ]
    if not source_blocks:
        return []

    source_ids = [block.pk for block in source_blocks]
    existing_source_ids = set(
        StudyBlock.objects.filter(
            week_start=target_start,
            carried_from_id__in=source_ids,
        ).values_list("carried_from_id", flat=True)
    )

    next_position = _carry_forward_position(target_start)
    carried_blocks = []
    for source in source_blocks:
        if source.pk in existing_source_ids:
            continue

        carried_block, _ = StudyBlock.objects.get_or_create(
            week_start=target_start,
            routine_key=f"carry-forward-{source.pk}",
            defaults={
                "date": target_date,
                "title": source.title,
                "planned_minutes": source.planned_minutes,
                "position": next_position,
                "status": StudyBlock.Status.PENDING,
                "carried_from": source,
                "assigned_concept": source.assigned_concept,
                "concept_assignment_source": source.concept_assignment_source,
            },
        )
        for assignment in StudyBlockProblem.objects.filter(
            study_block=source
        ).order_by("position", "id"):
            StudyBlockProblem.objects.get_or_create(
                study_block=carried_block,
                problem_id=assignment.problem_id,
                defaults={
                    "position": assignment.position,
                    "assignment_source": assignment.assignment_source,
                },
            )
        carried_blocks.append(carried_block)
        next_position += 1

    return carried_blocks


@transaction.atomic
def generate_weekly_routine(start_date: date | None = None) -> list[StudyBlock]:
    """Create the default routine for a week without duplicating its blocks."""

    week_start = week_start_for(start_date or timezone.localdate())
    generated_blocks: list[StudyBlock] = []

    for weekday, templates in _templates_for_week():
        block_date = week_start + timedelta(days=weekday)
        for position, (block_key, title, planned_minutes) in enumerate(templates):
            block, _ = StudyBlock.objects.get_or_create(
                week_start=week_start,
                routine_key=f"{weekday}-{block_key}",
                defaults={
                    "date": block_date,
                    "title": title,
                    "planned_minutes": planned_minutes,
                    "position": position,
                },
            )
            generated_blocks.append(block)

    carry_forward_unfinished_blocks(week_start)
    _normalize_carry_forward_positions(week_start)
    assign_weekday_problems(week_start)
    return generated_blocks


@transaction.atomic
def assign_recommended_concept(
    start_date: date | None = None,
    *,
    now=None,
) -> StudyBlock | None:
    """Assign the current recommendation to the next open concept block.

    The existing recommendation is returned when it is already assigned in the
    target week. That makes repeated Today/weekly-plan loads safe and prevents
    the same Concept from filling multiple routine blocks. A block with any
    existing assignment is excluded, so learner-selected Concepts are never
    replaced.
    """

    eligible_from = start_date or timezone.localdate()
    target_week_start = week_start_for(eligible_from)
    recommendation = recommend_next_concept(now=now)
    if recommendation is None:
        return None

    assigned = (
        StudyBlock.objects.select_for_update()
        .filter(
            week_start=target_week_start,
            assigned_concept_id=recommendation.concept.pk,
        )
        .order_by("date", "position", "id")
        .first()
    )
    if assigned is not None:
        return assigned

    candidate = (
        StudyBlock.objects.select_for_update()
        .filter(
            week_start=target_week_start,
            date__gte=eligible_from,
            routine_key__endswith="-concept",
            assigned_concept__isnull=True,
            status=StudyBlock.Status.PENDING,
        )
        .order_by("date", "position", "id")
        .first()
    )
    if candidate is None:
        return None

    candidate.assigned_concept = recommendation.concept
    candidate.concept_assignment_source = (
        StudyBlock.ConceptAssignmentSource.AUTOMATIC
    )
    candidate.save(
        update_fields=(
            "assigned_concept",
            "concept_assignment_source",
            "updated_at",
        )
    )
    return candidate


PROBLEMS_PER_WEEKDAY_BLOCK = 2
_AUTO_ASSIGNABLE_STATUSES = frozenset(
    {
        LearningStatus.UNSEEN,
        LearningStatus.ATTEMPTED,
        LearningStatus.SOLVED_WITH_HELP,
    }
)
_STATUS_PRIORITY = {
    LearningStatus.ATTEMPTED: 0,
    LearningStatus.SOLVED_WITH_HELP: 1,
    LearningStatus.UNSEEN: 2,
}


def _ready_concepts_for_problem_assignment() -> list[Concept]:
    """Return Concepts whose prerequisites have solid checkpoint evidence.

    The current product has no separate review model yet, so Concept readiness
    comes from the curriculum graph and Concept checkpoints. The Problem's
    Learning Status is applied separately when building the candidate pool.
    """

    concepts = list(
        Concept.objects.select_related("topic")
        .prefetch_related("prerequisites")
        .order_by("topic__display_order", "order", "id")
    )
    prerequisite_ids = {
        prerequisite.pk
        for concept in concepts
        for prerequisite in concept.prerequisites.all()
    }
    checkpoints = ConceptCheckpoint.objects.filter(
        concept_id__in={concept.pk for concept in concepts} | prerequisite_ids
    ).order_by("concept_id", "-submitted_at", "-id")
    latest_by_concept = {}
    for checkpoint in checkpoints:
        latest_by_concept.setdefault(checkpoint.concept_id, checkpoint)

    return [
        concept
        for concept in concepts
        if all(
            (
                checkpoint := latest_by_concept.get(prerequisite.pk)
            ) is not None
            and checkpoint.confidence >= ConceptCheckpoint.Confidence.SOLID
            for prerequisite in concept.prerequisites.all()
        )
    ]


def _problem_candidates_for_assignment() -> list[Problem]:
    """Return active Problems from ready, confirmed Concept classifications."""

    ready_concept_ids = {
        concept.pk for concept in _ready_concepts_for_problem_assignment()
    }
    if not ready_concept_ids:
        return []

    return list(
        Problem.objects.filter(is_active=True)
        .filter(
            Q(
                classifications__concept_id__in=ready_concept_ids,
                classifications__status=ProblemClassification.Status.CONFIRMED,
            )
            | Q(
                concept_id__in=ready_concept_ids,
                classifications__isnull=True,
            )
        )
        .distinct()
        .order_by("display_order", "title", "id")
    )


def _ordered_problem_candidates(
    problems: list[Problem],
    *,
    now=None,
) -> list[Problem]:
    """Rank candidates by due review, Learning Status, then catalog order."""

    if not problems:
        return []

    now = now or timezone.now()
    problem_ids = [problem.pk for problem in problems]
    statuses = dict(
        ProblemLearningStatus.objects.filter(
            problem_id__in=problem_ids
        ).values_list("problem_id", "status")
    )
    review_due_at = dict(
        ProblemReview.objects.filter(problem_id__in=problem_ids).values_list(
            "problem_id", "due_at"
        )
    )

    def is_due(problem: Problem) -> bool:
        due_at = review_due_at.get(problem.pk)
        return due_at is not None and due_at <= now

    return sorted(
        (
            problem
            for problem in problems
            if statuses.get(problem.pk, LearningStatus.UNSEEN)
            in _AUTO_ASSIGNABLE_STATUSES
            or is_due(problem)
        ),
        key=lambda problem: (
            0 if is_due(problem) else 1,
            _STATUS_PRIORITY.get(
                statuses.get(problem.pk, LearningStatus.UNSEEN),
                len(_STATUS_PRIORITY),
            ),
            review_due_at.get(problem.pk) or now,
            problem.display_order,
            problem.title.casefold(),
            problem.pk,
        ),
    )


@transaction.atomic
def assign_weekday_problems(
    start_date: date | None = None,
    *,
    now=None,
) -> list[StudyBlockProblem]:
    """Fill each weekday solve block with up to two eligible Problems.

    Automatic assignment is intentionally conservative: it never changes an
    existing assignment, skips Problems already used elsewhere in the target
    week, prioritizes due reviews and attempted/help-needed Problems, and
    leaves independently solved Problems with a future due date alone.
    Repeating this operation is therefore idempotent and safe to call from
    planner page loads.
    """

    now = now or timezone.now()
    target_week_start = week_start_for(start_date or timezone.localdate())
    solve_blocks = list(
        StudyBlock.objects.select_for_update()
        .filter(
            week_start=target_week_start,
            date__range=(target_week_start, target_week_start + timedelta(days=4)),
            routine_key__endswith="-problems",
            status=StudyBlock.Status.PENDING,
        )
        .order_by("date", "position", "id")
    )
    if not solve_blocks:
        return []

    candidates = _ordered_problem_candidates(
        _problem_candidates_for_assignment(),
        now=now,
    )
    assigned_problem_ids = set(
        StudyBlockProblem.objects.filter(
            study_block__week_start=target_week_start,
        ).values_list("problem_id", flat=True)
    )
    created_assignments: list[StudyBlockProblem] = []

    for block in solve_blocks:
        existing = list(
            StudyBlockProblem.objects.select_for_update()
            .filter(study_block=block)
            .order_by("position", "id")
        )
        if len(existing) >= PROBLEMS_PER_WEEKDAY_BLOCK:
            assigned_problem_ids.update(
                assignment.problem_id for assignment in existing
            )
            continue

        used_in_block = {assignment.problem_id for assignment in existing}
        next_position = (
            max((assignment.position for assignment in existing), default=-1) + 1
        )
        for problem in candidates:
            if len(existing) >= PROBLEMS_PER_WEEKDAY_BLOCK:
                break
            if problem.pk in used_in_block or problem.pk in assigned_problem_ids:
                continue

            assignment = StudyBlockProblem.objects.create(
                study_block=block,
                problem=problem,
                position=next_position,
                assignment_source=StudyBlockProblem.AssignmentSource.AUTOMATIC,
            )
            existing.append(assignment)
            created_assignments.append(assignment)
            used_in_block.add(problem.pk)
            assigned_problem_ids.add(problem.pk)
            next_position += 1

    return created_assignments


@transaction.atomic
def set_manual_problem_assignments(
    block: StudyBlock,
    problems: list[Problem],
) -> list[StudyBlockProblem]:
    """Replace one solve block's Problems after an explicit learner edit."""

    if not block.is_problem_solve_block:
        raise ValueError("Only weekday solve blocks can receive Problem assignments.")
    unique_problem_ids = list(dict.fromkeys(problem.pk for problem in problems))
    if len(unique_problem_ids) > PROBLEMS_PER_WEEKDAY_BLOCK:
        raise ValueError("Choose at most two Problems for one solve block.")
    if any(not problem.pk or not problem.is_active for problem in problems):
        raise ValueError("Manual assignments must use active catalog Problems.")

    StudyBlockProblem.objects.filter(study_block=block).delete()
    StudyBlockProblem.objects.bulk_create(
        [
            StudyBlockProblem(
                study_block=block,
                problem=problem,
                position=position,
                assignment_source=StudyBlockProblem.AssignmentSource.MANUAL,
            )
            for position, problem in enumerate(problems)
        ]
    )
    return list(
        StudyBlockProblem.objects.filter(study_block=block).order_by("position", "id")
    )


def is_weekly_routine_complete(value: date) -> bool:
    """Tell the Today view whether all default blocks exist for this week."""

    week_start = week_start_for(value)
    return (
        StudyBlock.objects.filter(week_start=week_start).count()
        >= DEFAULT_WEEKLY_ROUTINE_BLOCK_COUNT
    )


@transaction.atomic
def move_study_block(block: StudyBlock, direction: str) -> bool:
    """Move a block one position up or down within its own calendar day."""

    if direction not in {"up", "down"}:
        return False

    blocks = list(
        StudyBlock.objects.select_for_update()
        .filter(date=block.date)
        .order_by("position", "id")
    )
    if not blocks:
        return False

    # Normalize first so older/manual rows with duplicate default positions still
    # get deterministic ordering and future moves remain contiguous.
    for position, item in enumerate(blocks):
        if item.position != position:
            item.position = position
    StudyBlock.objects.bulk_update(blocks, ["position"])

    try:
        current_index = next(
            index for index, item in enumerate(blocks) if item.pk == block.pk
        )
    except StopIteration:
        return False

    swap_index = current_index - 1 if direction == "up" else current_index + 1
    if not 0 <= swap_index < len(blocks):
        return False

    blocks[current_index].position, blocks[swap_index].position = (
        blocks[swap_index].position,
        blocks[current_index].position,
    )
    StudyBlock.objects.bulk_update(
        [blocks[current_index], blocks[swap_index]],
        ["position"],
    )
    return True


def _transition_time(value=None):
    return value or timezone.now()


def _current_elapsed_seconds(session: WorkSession, now) -> int:
    return session.elapsed_seconds_at(now)


def format_elapsed_seconds(seconds: int) -> str:
    """Format an elapsed duration for the learner-facing timer readout."""

    hours, remainder = divmod(max(0, seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


@transaction.atomic
def start_work_session(block: StudyBlock, now=None) -> WorkSession:
    """Start a new timer run, allowing a fresh run after a stopped session."""

    locked_block = StudyBlock.objects.select_for_update().get(pk=block.pk)
    if WorkSession.objects.filter(
        study_block=locked_block,
        status__in=(WorkSession.Status.RUNNING, WorkSession.Status.PAUSED),
    ).exists():
        raise ActiveWorkSessionError("This study block already has an active timer.")

    started_at = _transition_time(now)
    try:
        # Keep the insert in a savepoint so the conditional unique constraint can
        # protect against a concurrent start even on databases where row locks
        # do not serialize the two requests.
        with transaction.atomic():
            return WorkSession.objects.create(
                study_block=locked_block,
                status=WorkSession.Status.RUNNING,
                started_at=started_at,
                last_resumed_at=started_at,
            )
    except IntegrityError as error:
        raise ActiveWorkSessionError(
            "This study block already has an active timer."
        ) from error


@transaction.atomic
def pause_work_session(session: WorkSession, now=None) -> WorkSession:
    """Persist the current run segment and pause the timer."""

    locked_session = WorkSession.objects.select_for_update().get(pk=session.pk)
    if locked_session.status != WorkSession.Status.RUNNING:
        raise InvalidWorkSessionStateError("Only a running timer can be paused.")

    paused_at = _transition_time(now)
    locked_session.elapsed_seconds = _current_elapsed_seconds(
        locked_session,
        paused_at,
    )
    locked_session.status = WorkSession.Status.PAUSED
    locked_session.paused_at = paused_at
    locked_session.save(
        update_fields=(
            "elapsed_seconds",
            "status",
            "paused_at",
            "updated_at",
        )
    )
    return locked_session


@transaction.atomic
def resume_work_session(session: WorkSession, now=None) -> WorkSession:
    """Resume a paused timer without losing its persisted elapsed time."""

    locked_session = WorkSession.objects.select_for_update().get(pk=session.pk)
    if locked_session.status != WorkSession.Status.PAUSED:
        raise InvalidWorkSessionStateError("Only a paused timer can be resumed.")

    resumed_at = _transition_time(now)
    locked_session.status = WorkSession.Status.RUNNING
    locked_session.last_resumed_at = resumed_at
    locked_session.paused_at = None
    locked_session.save(
        update_fields=(
            "status",
            "last_resumed_at",
            "paused_at",
            "updated_at",
        )
    )
    return locked_session


@transaction.atomic
def stop_work_session(
    session: WorkSession,
    now=None,
    *,
    complete_block: bool = False,
) -> WorkSession:
    """Stop a timer and optionally complete its block by explicit choice."""

    locked_session = WorkSession.objects.select_for_update().get(pk=session.pk)
    if locked_session.status not in {
        WorkSession.Status.RUNNING,
        WorkSession.Status.PAUSED,
    }:
        raise InvalidWorkSessionStateError(
            "Only a running or paused timer can be stopped."
        )

    stopped_at = _transition_time(now)
    locked_session.elapsed_seconds = _current_elapsed_seconds(
        locked_session,
        stopped_at,
    )
    locked_session.status = WorkSession.Status.STOPPED
    locked_session.stopped_at = stopped_at
    locked_session.save(
        update_fields=(
            "elapsed_seconds",
            "status",
            "stopped_at",
            "updated_at",
        )
    )

    if complete_block:
        block = StudyBlock.objects.select_for_update().get(
            pk=locked_session.study_block_id
        )
        block.status = StudyBlock.Status.COMPLETED
        block.save(update_fields=("status", "updated_at"))

    return locked_session
