from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("problems", "0002_problemclassification"),
    ]

    operations = [
        migrations.AddField(
            model_name="problem",
            name="is_paid_only",
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name="CatalogSync",
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
                ("source_name", models.CharField(default="LeetCode", max_length=100)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("running", "Syncing"),
                            ("succeeded", "Completed"),
                            ("failed", "Failed"),
                        ],
                        default="running",
                        max_length=20,
                    ),
                ),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("last_success_at", models.DateTimeField(blank=True, null=True)),
                ("total_items", models.PositiveIntegerField(default=0)),
                ("processed_items", models.PositiveIntegerField(default=0)),
                ("imported_count", models.PositiveIntegerField(default=0)),
                ("updated_count", models.PositiveIntegerField(default=0)),
                ("deactivated_count", models.PositiveIntegerField(default=0)),
                (
                    "classification_warning_count",
                    models.PositiveIntegerField(default=0),
                ),
                ("current_batch", models.PositiveIntegerField(default=0)),
                ("error_message", models.TextField(blank=True)),
            ],
            options={
                "ordering": ("-started_at", "-id"),
                "indexes": [
                    models.Index(
                        fields=["source_name", "status"],
                        name="problems_ca_source__19df56_idx",
                    ),
                    models.Index(
                        fields=["source_name", "-started_at"],
                        name="problems_ca_source__0e1146_idx",
                    ),
                ],
            },
        ),
    ]
