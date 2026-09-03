# Generated manually for the standalone problems vertical slice.
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("curriculum", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Problem",
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
                ("title", models.CharField(max_length=220)),
                ("slug", models.SlugField(max_length=240, unique=True)),
                ("statement", models.TextField()),
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
                ("source_problem_id", models.CharField(blank=True, max_length=100)),
                ("source_url", models.URLField(blank=True)),
                ("examples", models.JSONField(blank=True, default=list)),
                ("tags", models.JSONField(blank=True, default=list)),
                (
                    "display_order",
                    models.PositiveIntegerField(
                        default=1,
                        validators=[django.core.validators.MinValueValidator(1)],
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "concept",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="problems",
                        to="curriculum.concept",
                    ),
                ),
            ],
            options={
                "ordering": ("title", "id"),
                "indexes": [
                    models.Index(
                        fields=["difficulty", "is_active"],
                        name="problems_pr_difficu_ba7ee7_idx",
                    ),
                    models.Index(
                        fields=["concept", "is_active"],
                        name="problems_pr_concept_2d1b81_idx",
                    ),
                ],
            },
        ),
    ]
