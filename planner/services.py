from datetime import date, timedelta

from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from .models import RestDay, StudyBlock, WorkSession


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
    return generated_blocks


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
