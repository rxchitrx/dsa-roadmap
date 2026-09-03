import pytest
from django.urls import reverse
from django.utils import timezone

from planner.models import StudyBlock
from planner.services import generate_weekly_routine, week_start_for


@pytest.fixture
def current_week_blocks():
    week_start = week_start_for(timezone.localdate())
    generate_weekly_routine(week_start)
    return list(
        StudyBlock.objects.filter(week_start=week_start).order_by(
            "date", "position", "id"
        )
    )


@pytest.mark.django_db
def test_weekly_plan_shows_all_days_and_editable_fields(client, current_week_blocks):
    response = client.get(reverse("planner:weekly_plan"))

    assert response.status_code == 200
    assert len(response.context["days"]) == 7
    assert response.content.decode().count('data-testid="weekly-block"') == 37
    assert 'data-testid="edit-title"' in response.content.decode()
    assert 'data-testid="edit-duration"' in response.content.decode()


@pytest.mark.django_db
def test_edit_persists_title_and_duration_and_is_visible_after_reload(
    client, current_week_blocks
):
    block = next(
        block for block in current_week_blocks if block.date == timezone.localdate()
    )

    response = client.post(
        reverse("planner:edit_study_block", args=[block.pk]),
        {"title": "Re-solve a sliding window question", "planned_minutes": "35"},
    )

    assert response.status_code == 302
    block.refresh_from_db()
    assert block.title == "Re-solve a sliding window question"
    assert block.planned_minutes == 35

    reloaded = client.get(reverse("planner:weekly_plan"))
    html = reloaded.content.decode()
    assert 'value="Re-solve a sliding window question"' in html
    assert 'value="35"' in html

    today = client.get(reverse("planner:today"))
    today_html = today.content.decode()
    assert "Re-solve a sliding window question" in today_html
    assert "35 min planned" in today_html


@pytest.mark.django_db
def test_reorder_stays_within_the_day_and_today_uses_the_persisted_order(
    client, current_week_blocks
):
    today = timezone.localdate()
    today_blocks = [block for block in current_week_blocks if block.date == today]
    first_block, second_block = today_blocks[:2]

    response = client.post(
        reverse("planner:reorder_study_block", args=[second_block.pk]),
        {"direction": "up"},
    )

    assert response.status_code == 302
    ordered_today = list(
        StudyBlock.objects.filter(date=today).order_by("position", "id")
    )
    assert [block.pk for block in ordered_today[:2]] == [second_block.pk, first_block.pk]
    assert [block.position for block in ordered_today] == list(range(len(ordered_today)))

    today_response = client.get(reverse("planner:today"))
    assert list(today_response.context["study_blocks"][:2]) == ordered_today[:2]


@pytest.mark.django_db
@pytest.mark.parametrize("duration", ["0", "-10", "not-a-number", ""])
def test_non_positive_or_invalid_duration_is_rejected(client, current_week_blocks, duration):
    block = current_week_blocks[0]
    original = (block.title, block.planned_minutes)

    response = client.post(
        reverse("planner:edit_study_block", args=[block.pk]),
        {"title": "Attempted edit", "planned_minutes": duration},
    )

    assert response.status_code == 400
    html = response.content.decode()
    assert 'data-testid="edit-errors"' in html
    assert "minute" in html.lower()
    block.refresh_from_db()
    assert (block.title, block.planned_minutes) == original


@pytest.mark.django_db
def test_move_down_persists_across_weekly_plan_reload(client, current_week_blocks):
    block = current_week_blocks[0]
    sibling = current_week_blocks[1]

    client.post(
        reverse("planner:reorder_study_block", args=[block.pk]),
        {"direction": "down"},
    )

    reloaded = client.get(reverse("planner:weekly_plan"))
    monday_items = reloaded.context["days"][0]["items"]
    assert [item["block"].pk for item in monday_items[:2]] == [sibling.pk, block.pk]


@pytest.mark.django_db
def test_reorder_rejects_unknown_direction(client, current_week_blocks):
    response = client.post(
        reverse("planner:reorder_study_block", args=[current_week_blocks[0].pk]),
        {"direction": "sideways"},
    )

    assert response.status_code == 400
