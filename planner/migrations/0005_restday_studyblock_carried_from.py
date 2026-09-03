import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("planner", "0004_worksession"),
    ]

    operations = [
        migrations.AddField(
            model_name="studyblock",
            name="carried_from",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="carry_forward_blocks",
                to="planner.studyblock",
            ),
        ),
        migrations.CreateModel(
            name="RestDay",
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
                ("date", models.DateField(unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ("date", "id"),
            },
        ),
    ]
