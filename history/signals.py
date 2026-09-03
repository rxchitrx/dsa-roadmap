from django.db.models.signals import post_save
from django.dispatch import receiver

from practice.models import PracticeRun
from problems.services import ensure_problem_snapshot

from .models import RunHistoryEntry


@receiver(post_save, sender=PracticeRun)
def snapshot_new_practice_run(sender, instance, created, **kwargs):
    """Capture executions only; draft saves do not emit this signal."""

    if created:
        problem_snapshot, _created = ensure_problem_snapshot(instance.problem)
        RunHistoryEntry.objects.get_or_create(
            practice_run=instance,
            defaults={
                "problem_snapshot": problem_snapshot,
                "code_snapshot": instance.code,
                "status": instance.status,
                "result_summary": instance.summary,
                "passed_tests": instance.passed_tests,
                "total_tests": instance.total_tests,
                "duration_ms": instance.duration_ms,
                "captured_at": instance.created_at,
            },
        )
