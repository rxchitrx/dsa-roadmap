from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("practice", "0004_solutionreflection"),
        ("problems", "0004_problemsnapshot"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProblemLearningStatus",
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
                            ("unseen", "Unseen"),
                            ("attempted", "Attempted — couldn't solve yet"),
                            ("solved_with_help", "Solved with help"),
                            ("solved_independently", "Solved independently"),
                        ],
                        default="unseen",
                        max_length=32,
                    ),
                ),
                ("reason", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "problem",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="learning_status",
                        to="problems.problem",
                    ),
                ),
            ],
            options={"ordering": ("-updated_at", "-id")},
        ),
        migrations.CreateModel(
            name="LearningStatusEvent",
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
                            ("unseen", "Unseen"),
                            ("attempted", "Attempted — couldn't solve yet"),
                            ("solved_with_help", "Solved with help"),
                            ("solved_independently", "Solved independently"),
                        ],
                        max_length=32,
                    ),
                ),
                ("reason", models.TextField()),
                ("changed_at", models.DateTimeField(db_index=True, auto_now_add=True)),
                (
                    "learning_status",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="events",
                        to="practice.problemlearningstatus",
                    ),
                ),
                (
                    "practice_run",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="learning_status_events",
                        to="practice.practicerun",
                    ),
                ),
                (
                    "problem_snapshot",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="learning_status_events",
                        to="problems.problemsnapshot",
                    ),
                ),
                (
                    "reflection",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="learning_status_events",
                        to="practice.solutionreflection",
                    ),
                ),
            ],
            options={
                "ordering": ("-changed_at", "-id"),
                "indexes": [
                    models.Index(
                        fields=["learning_status", "-changed_at"],
                        name="practice_le_learnin_877123_idx",
                    ),
                    models.Index(
                        fields=["status", "-changed_at"],
                        name="practice_le_status_61d54c_idx",
                    ),
                ],
            },
        ),
    ]
