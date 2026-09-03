from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("practice", "0003_customtestcase"),
    ]

    operations = [
        migrations.CreateModel(
            name="SolutionReflection",
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
                ("rewritten_approach", models.TextField()),
                ("complexity", models.TextField()),
                ("mistake_cause", models.TextField()),
                ("next_correction", models.TextField()),
                ("notes", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "practice_run",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reflection",
                        to="practice.practicerun",
                    ),
                ),
            ],
            options={"ordering": ("-updated_at", "-id")},
        ),
    ]
