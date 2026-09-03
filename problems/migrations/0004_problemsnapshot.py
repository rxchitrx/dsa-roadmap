from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q
import django.utils.timezone


SNAPSHOT_FIELDS = (
    "title",
    "slug",
    "statement",
    "difficulty",
    "source_name",
    "source_problem_id",
    "source_url",
    "is_paid_only",
    "examples",
    "tags",
)


def create_initial_snapshots(apps, schema_editor):
    Problem = apps.get_model("problems", "Problem")
    ProblemSnapshot = apps.get_model("problems", "ProblemSnapshot")

    for problem in Problem.objects.all().iterator():
        ProblemSnapshot.objects.create(
            problem_id=problem.pk,
            version=1,
            **{
                field_name: getattr(problem, field_name)
                for field_name in SNAPSHOT_FIELDS
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("problems", "0003_catalogsync_problem_is_paid_only"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProblemSnapshot",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("version", models.PositiveIntegerField()),
                ("title", models.CharField(max_length=220)),
                ("slug", models.SlugField(max_length=240)),
                (
                    "statement",
                    models.TextField(),
                ),
                (
                    "difficulty",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("easy", "Easy"),
                            ("medium", "Medium"),
                            ("hard", "Hard"),
                        ],
                        max_length=20,
                    ),
                ),
                ("source_name", models.CharField(blank=True, max_length=100)),
                (
                    "source_problem_id",
                    models.CharField(blank=True, max_length=100),
                ),
                ("source_url", models.URLField(blank=True)),
                ("is_paid_only", models.BooleanField(default=False)),
                ("examples", models.JSONField(blank=True, default=list)),
                ("tags", models.JSONField(blank=True, default=list)),
                (
                    "is_active",
                    models.BooleanField(db_index=True, default=True),
                ),
                (
                    "captured_at",
                    models.DateTimeField(
                        db_index=True,
                        default=django.utils.timezone.now,
                    ),
                ),
                (
                    "problem",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="snapshots",
                        to="problems.problem",
                    ),
                ),
            ],
            options={
                "ordering": ("problem_id", "-version", "-id"),
                "indexes": [
                    models.Index(
                        fields=["problem", "-captured_at"],
                        name="problems_pr_problem_6c1e6e_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("problem", "version"),
                        name="unique_problem_snapshot_version",
                    ),
                    models.UniqueConstraint(
                        condition=Q(is_active=True),
                        fields=("problem",),
                        name="one_active_problem_snapshot",
                    ),
                ],
            },
        ),
        migrations.RunPython(create_initial_snapshots, migrations.RunPython.noop),
    ]
