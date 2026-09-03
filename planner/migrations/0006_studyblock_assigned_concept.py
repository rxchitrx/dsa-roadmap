import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("curriculum", "0001_initial"),
        ("planner", "0005_restday_studyblock_carried_from"),
    ]

    operations = [
        migrations.AddField(
            model_name="studyblock",
            name="assigned_concept",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="study_blocks",
                to="curriculum.concept",
            ),
        ),
        migrations.AddField(
            model_name="studyblock",
            name="concept_assignment_source",
            field=models.CharField(
                blank=True,
                choices=[
                    ("automatic", "Recommended"),
                    ("manual", "Selected by you"),
                ],
                default="",
                max_length=20,
            ),
        ),
    ]
