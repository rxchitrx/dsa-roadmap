from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("problems", "0004_problemsnapshot"),
    ]

    operations = [
        migrations.CreateModel(
            name="AssessmentPool",
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
                ("week_start", models.DateField(unique=True)),
                (
                    "requested_problem_count",
                    models.PositiveSmallIntegerField(
                        default=3,
                        validators=[django.core.validators.MinValueValidator(1)],
                    ),
                ),
                (
                    "duration_minutes",
                    models.PositiveIntegerField(
                        default=90,
                        validators=[django.core.validators.MinValueValidator(1)],
                    ),
                ),
                ("rationale", models.TextField(blank=True)),
                ("eligibility_metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ("-week_start", "-id"),
            },
        ),
        migrations.CreateModel(
            name="AssessmentSelection",
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
                    "position",
                    models.PositiveSmallIntegerField(),
                ),
                (
                    "slot_kind",
                    models.CharField(
                        choices=[
                            ("easy", "Easy"),
                            ("medium", "Medium"),
                        ],
                        max_length=20,
                    ),
                ),
                ("is_unseen", models.BooleanField(default=True)),
                ("rationale", models.TextField()),
                ("eligibility_metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "pool",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="selections",
                        to="assessments.assessmentpool",
                    ),
                ),
                (
                    "problem",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="assessment_selections",
                        to="problems.problem",
                    ),
                ),
            ],
            options={
                "ordering": ("position", "id"),
                "indexes": [
                    models.Index(
                        fields=["pool", "slot_kind"],
                        name="assessments_pool_slot_kind_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("pool", "problem"),
                        name="unique_assessment_pool_problem",
                    ),
                    models.UniqueConstraint(
                        fields=("pool", "position"),
                        name="unique_assessment_pool_position",
                    ),
                ],
            },
        ),
    ]
