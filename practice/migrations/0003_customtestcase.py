from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("practice", "0002_practicerun"),
    ]

    operations = [
        migrations.CreateModel(
            name="CustomTestCase",
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
                ("label", models.CharField(max_length=120)),
                ("input_data", models.JSONField(default=list)),
                ("expected_output", models.JSONField(null=True)),
                ("position", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "problem",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="custom_practice_tests",
                        to="problems.problem",
                    ),
                ),
            ],
            options={
                "ordering": ("position", "created_at", "id"),
                "indexes": [
                    models.Index(
                        fields=["problem", "position"],
                        name="practice_cu_problem_37c986_idx",
                    ),
                ],
            },
        ),
    ]
