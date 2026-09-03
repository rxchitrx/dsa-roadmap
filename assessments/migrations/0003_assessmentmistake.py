from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("assessments", "0002_assessmentsession_assessmentresponse"),
    ]

    operations = [
        migrations.CreateModel(
            name="AssessmentMistake",
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
                    "cause",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("concept_gap", "Concept gap"),
                            ("wrong_pattern", "Wrong pattern"),
                            ("implementation_bug", "Implementation bug"),
                            ("edge_case_miss", "Missed an edge case"),
                            ("complexity_miss", "Complexity mistake"),
                            ("rushed_or_incomplete", "Rushed or incomplete"),
                            ("other", "Other"),
                        ],
                        max_length=32,
                    ),
                ),
                ("corrected_approach", models.TextField(blank=True)),
                ("next_action", models.TextField(blank=True)),
                ("is_complete", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "assessment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="mistakes",
                        to="assessments.assessmentsession",
                    ),
                ),
                (
                    "problem",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="assessment_mistakes",
                        to="problems.problem",
                    ),
                ),
                (
                    "response",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="mistake",
                        to="assessments.assessmentresponse",
                    ),
                ),
            ],
            options={
                "ordering": ("response__selection__position", "id"),
                "indexes": [
                    models.Index(
                        fields=["assessment", "is_complete"],
                        name="assess_mistake_status_idx",
                    ),
                ],
            },
        ),
    ]
