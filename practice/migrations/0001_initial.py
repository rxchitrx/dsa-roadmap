from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("problems", "0002_problemclassification"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProblemDraft",
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
                ("starter_signature", models.CharField(max_length=240)),
                ("code", models.TextField()),
                ("revision", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "problem",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="python_draft",
                        to="problems.problem",
                    ),
                ),
            ],
            options={"ordering": ("-updated_at", "-id")},
        ),
    ]
