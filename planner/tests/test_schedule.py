from collections import Counter
from datetime import date

import pytest

from planner.models import StudyBlock
from planner.services import generate_weekly_routine


MONDAY = date(2026, 9, 7)


@pytest.mark.django_db
def test_default_routine_creates_expected_blocks_durations_and_day_assignments():
    blocks = generate_weekly_routine(MONDAY)

    assert len(blocks) == 37
    assert StudyBlock.objects.filter(week_start=MONDAY).count() == 37
    assert Counter(block.date.weekday() for block in blocks) == {
        0: 6,
        1: 6,
        2: 6,
        3: 6,
        4: 6,
        5: 3,
        6: 4,
    }

    expected_durations = {
        0: [20, 30, 50, 20, 30, 30],
        1: [20, 30, 50, 20, 30, 30],
        2: [20, 30, 50, 20, 30, 30],
        3: [20, 30, 50, 20, 30, 30],
        4: [20, 30, 50, 20, 30, 30],
        5: [90, 30, 120],
        6: [100, 30, 120, 30],
    }
    for weekday, durations in expected_durations.items():
        assert [
            block.planned_minutes
            for block in blocks
            if block.date.weekday() == weekday
        ] == durations

    assert [block.position for block in blocks if block.date.weekday() == 0] == list(
        range(6)
    )


@pytest.mark.django_db
def test_generating_the_same_week_twice_does_not_duplicate_or_reorder_blocks():
    first_run = generate_weekly_routine(MONDAY)
    first_identity = [
        (block.pk, block.date, block.routine_key, block.position)
        for block in first_run
    ]

    second_run = generate_weekly_routine(MONDAY)
    second_identity = [
        (block.pk, block.date, block.routine_key, block.position)
        for block in second_run
    ]

    assert StudyBlock.objects.filter(week_start=MONDAY).count() == 37
    assert second_identity == first_identity


@pytest.mark.django_db
def test_generate_routine_action_creates_the_current_week_and_redirects(client, settings):
    settings.TIME_ZONE = "UTC"

    response = client.post("/routine/generate/")
    repeat_response = client.post("/routine/generate/")

    assert response.status_code == 302
    assert repeat_response.status_code == 302
    assert response.url == "/"
    assert StudyBlock.objects.count() == 37
