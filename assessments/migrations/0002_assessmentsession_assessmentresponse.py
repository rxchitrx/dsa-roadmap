from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("assessments", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AssessmentSession",
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
                    "duration_minutes",
                    models.PositiveIntegerField(
                        default=90,
                        validators=[django.core.validators.MinValueValidator(1)],
                    ),
                ),
                ("started_at", models.DateTimeField()),
                ("cutoff_at", models.DateTimeField()),
                ("cutoff_recorded_at", models.DateTimeField(blank=True, null=True)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("current_position", models.PositiveSmallIntegerField(default=1)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("in_progress", "In progress"),
                            ("overtime", "Overtime"),
                            ("completed", "Completed"),
                        ],
                        default="in_progress",
                        max_length=20,
                    ),
                ),
                ("cutoff_snapshot", models.JSONField(blank=True, default=dict)),
                ("final_summary", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "pool",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="session",
                        to="assessments.assessmentpool",
                    ),
                ),
            ],
            options={"ordering": ("-started_at", "-id")},
        ),
        migrations.CreateModel(
            name="AssessmentResponse",
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
                ("draft_answer", models.TextField(blank=True)),
                (
                    "outcome",
                    models.CharField(
                        choices=[
                            ("not_started", "Not started"),
                            ("in_progress", "In progress"),
                            ("solved", "Solved"),
                            ("needs_review", "Needs review"),
                            ("skipped", "Skipped"),
                        ],
                        default="not_started",
                        max_length=20,
                    ),
                ),
                ("result_note", models.TextField(blank=True)),
                ("cutoff_draft_answer", models.TextField(blank=True, null=True)),
                (
                    "cutoff_outcome",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("not_started", "Not started"),
                            ("in_progress", "In progress"),
                            ("solved", "Solved"),
                            ("needs_review", "Needs review"),
                            ("skipped", "Skipped"),
                        ],
                        max_length=20,
                        null=True,
                    ),
                ),
                ("cutoff_result_note", models.TextField(blank=True, null=True)),
                ("cutoff_recorded_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "selection",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="response",
                        to="assessments.assessmentselection",
                    ),
                ),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="responses",
                        to="assessments.assessmentsession",
                    ),
                ),
            ],
            options={
                "ordering": ("selection__position", "id"),
                "indexes": [
                    models.Index(
                        fields=["session", "outcome"],
                        name="assess_session_outcome_idx",
                    ),
                ],
            },
        ),
    ]
