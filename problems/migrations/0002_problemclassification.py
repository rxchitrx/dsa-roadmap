from django.db import migrations, models
import django.db.models.deletion


def backfill_primary_classifications(apps, schema_editor):
    Problem = apps.get_model("problems", "Problem")
    ProblemClassification = apps.get_model("problems", "ProblemClassification")

    ProblemClassification.objects.bulk_create(
        [
            ProblemClassification(
                problem_id=problem.pk,
                concept_id=problem.concept_id,
                status="confirmed",
            )
            for problem in Problem.objects.exclude(concept_id__isnull=True).iterator()
        ],
        ignore_conflicts=True,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("problems", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProblemClassification",
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
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("confirmed", "Confirmed"),
                            ("uncertain", "Uncertain"),
                            ("fallback", "Fallback"),
                        ],
                        default="confirmed",
                        max_length=20,
                    ),
                ),
                (
                    "note",
                    models.CharField(
                        blank=True,
                        help_text="Explain why an uncertain or fallback classification was chosen.",
                        max_length=500,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "concept",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="problem_classifications",
                        to="curriculum.concept",
                    ),
                ),
                (
                    "problem",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="classifications",
                        to="problems.problem",
                    ),
                ),
            ],
            options={
                "ordering": ("concept__topic", "concept__order", "concept__name", "id"),
                "indexes": [
                    models.Index(
                        fields=["problem", "status"],
                        name="problems_pr_problem_57db6b_idx",
                    ),
                    models.Index(
                        fields=["concept", "status"],
                        name="problems_pr_concept_0c7f21_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("problem", "concept"),
                        name="unique_problem_concept_classification",
                    ),
                ],
            },
        ),
        migrations.AddField(
            model_name="problem",
            name="concepts",
            field=models.ManyToManyField(
                blank=True,
                related_name="classified_problems",
                through="problems.ProblemClassification",
                to="curriculum.concept",
            ),
        ),
        migrations.RunPython(
            backfill_primary_classifications,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
