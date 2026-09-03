from datetime import date

import pytest

from planner.models import StudyBlock


@pytest.mark.django_db
def test_study_block_persists_date_plan_and_default_status():
    block = StudyBlock.objects.create(
        date=date(2026, 9, 3),
        title="Re-solve an old question",
        planned_minutes=20,
    )

    saved_block = StudyBlock.objects.get(pk=block.pk)

    assert saved_block.date == date(2026, 9, 3)
    assert saved_block.title == "Re-solve an old question"
    assert saved_block.planned_minutes == 20
    assert saved_block.status == StudyBlock.Status.PENDING
    assert str(saved_block) == "Re-solve an old question (2026-09-03)"


@pytest.mark.django_db
def test_study_block_can_be_marked_completed():
    block = StudyBlock.objects.create(
        date=date(2026, 9, 3),
        title="Learn one concept",
        planned_minutes=30,
        status=StudyBlock.Status.COMPLETED,
    )

    assert block.get_status_display() == "Completed"
