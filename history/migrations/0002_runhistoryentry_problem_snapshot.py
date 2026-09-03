from django.db import migrations, models
import django.db.models.deletion


def attach_current_snapshots(apps, schema_editor):
    RunHistoryEntry = apps.get_model("history", "RunHistoryEntry")
    ProblemSnapshot = apps.get_model("problems", "ProblemSnapshot")

    for entry in RunHistoryEntry.objects.select_related("practice_run").filter(
        problem_snapshot__isnull=True
    ).iterator():
        snapshot = (
            ProblemSnapshot.objects.filter(
                problem_id=entry.practice_run.problem_id,
                is_active=True,
            )
            .order_by("-version", "-id")
            .first()
        )
        if snapshot is not None:
            RunHistoryEntry.objects.filter(pk=entry.pk).update(
                problem_snapshot_id=snapshot.pk
            )


class Migration(migrations.Migration):
    dependencies = [
        ("history", "0001_initial"),
        ("problems", "0004_problemsnapshot"),
    ]

    operations = [
        migrations.AddField(
            model_name="runhistoryentry",
            name="problem_snapshot",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="history_entries",
                to="problems.problemsnapshot",
            ),
        ),
        migrations.RunPython(attach_current_snapshots, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="runhistoryentry",
            name="problem_snapshot",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="history_entries",
                to="problems.problemsnapshot",
            ),
        ),
    ]
