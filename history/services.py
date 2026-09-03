from django.db import transaction

from practice.models import PracticeRun

from .models import RunHistoryEntry


@transaction.atomic
def ensure_history_entries(runs):
    """Materialize entries for runs created before the history app existed."""

    runs = list(runs)
    if not runs:
        return []

    run_ids = [run.pk for run in runs]
    existing_ids = set(
        RunHistoryEntry.objects.filter(practice_run_id__in=run_ids).values_list(
            "practice_run_id", flat=True
        )
    )
    missing = [run for run in runs if run.pk not in existing_ids]
    if missing:
        RunHistoryEntry.objects.bulk_create(
            [RunHistoryEntry.snapshot_for(run) for run in missing],
            ignore_conflicts=True,
        )

    return list(
        RunHistoryEntry.objects.filter(practice_run_id__in=run_ids)
        .select_related("practice_run__problem")
        .order_by("-captured_at", "-id")
    )


def history_for_problem(problem_slug=""):
    runs = PracticeRun.objects.select_related("problem")
    if problem_slug:
        runs = runs.filter(problem__slug=problem_slug)
    return ensure_history_entries(runs.order_by("-created_at", "-id"))
