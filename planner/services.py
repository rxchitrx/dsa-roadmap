from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from .models import StudyBlock


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

    return generated_blocks


def is_weekly_routine_complete(value: date) -> bool:
    """Tell the Today view whether all default blocks exist for this week."""

    week_start = week_start_for(value)
    return (
        StudyBlock.objects.filter(week_start=week_start).count()
        == DEFAULT_WEEKLY_ROUTINE_BLOCK_COUNT
    )
