from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from planner.models import RestDay, StudyBlock, WorkSession
from planner.services import (
    carry_forward_unfinished_blocks,
    generate_weekly_routine,
    toggle_rest_day,
    week_start_for,
)


@pytest.fixture
def current_week_start():
    return week_start_for(timezone.localdate())


@pytest.mark.django_db
def test_rollover_copies_pending_block_without_mutating_source_or_history(
    current_week_start,
):
    previous_week_start = current_week_start - timedelta(days=7)
    source = StudyBlock.objects.create(
        date=previous_week_start + timedelta(days=2),
        week_start=previous_week_start,
        routine_key="old-concept",
        position=1,
        title="Re-solve graph traversal",
        planned_minutes=35,
    )
    session = WorkSession.objects.create(
        study_block=source,
        status=WorkSession.Status.STOPPED,
        started_at=timezone.now(),
        last_resumed_at=timezone.now(),
        stopped_at=timezone.now(),
        elapsed_seconds=420,
    )
    original_values = {
        "date": source.date,
        "week_start": source.week_start,
        "status": source.status,
        "title": source.title,
    }

    carried = carry_forward_unfinished_blocks(current_week_start)

    assert len(carried) == 1
    copy = carried[0]
    assert copy.pk != source.pk
    assert copy.date == current_week_start
    assert copy.week_start == current_week_start
    assert copy.carried_from_id == source.pk
    assert copy.status == StudyBlock.Status.PENDING
    assert copy.title == source.title
    assert copy.work_sessions.count() == 0

    source.refresh_from_db()
    assert {
        "date": source.date,
        "week_start": source.week_start,
        "status": source.status,
        "title": source.title,
    } == original_values
    assert WorkSession.objects.filter(pk=session.pk, study_block=source).exists()


@pytest.mark.django_db
def test_rollover_is_idempotent_and_does_not_carry_completed_or_rest_day_work(
    current_week_start,
):
    previous_week_start = current_week_start - timedelta(days=7)
    pending = StudyBlock.objects.create(
        date=previous_week_start,
        week_start=previous_week_start,
        routine_key="pending",
        title="Pending question",
        planned_minutes=20,
    )
    StudyBlock.objects.create(
        date=previous_week_start + timedelta(days=1),
        week_start=previous_week_start,
        routine_key="completed",
        title="Completed question",
        planned_minutes=20,
        status=StudyBlock.Status.COMPLETED,
    )
    rest_day_date = previous_week_start + timedelta(days=2)
    RestDay.objects.create(date=rest_day_date)
    StudyBlock.objects.create(
        date=rest_day_date,
        week_start=previous_week_start,
        routine_key="rest-day-work",
        title="Skipped on rest day",
        planned_minutes=20,
    )

    first_run = carry_forward_unfinished_blocks(current_week_start)
    second_run = carry_forward_unfinished_blocks(current_week_start)

    assert [block.carried_from_id for block in first_run] == [pending.pk]
    assert second_run == []
    assert StudyBlock.objects.filter(
        week_start=current_week_start,
        carried_from__isnull=False,
    ).count() == 1


@pytest.mark.django_db
def test_next_week_planning_view_shows_carry_forward_work(current_week_start, client):
    previous_week_start = current_week_start - timedelta(days=7)
    StudyBlock.objects.create(
        date=previous_week_start + timedelta(days=4),
        week_start=previous_week_start,
        routine_key="old-problems",
        title="Finish the old problems",
        planned_minutes=50,
    )
    generate_weekly_routine(current_week_start)

    response = client.get(reverse("planner:weekly_plan"))

    assert response.status_code == 200
    monday = response.context["days"][0]
    assert any(
        item["block"].title == "Finish the old problems"
        and item["block"].is_carried_forward
        for item in monday["items"]
    )
    assert 'data-testid="carry-forward-label"' in response.content.decode()


@pytest.mark.django_db
def test_rest_day_hides_planned_work_but_preserves_it_across_reload(client):
    today = timezone.localdate()
    block = StudyBlock.objects.create(
        date=today,
        title="Solve one array problem",
        planned_minutes=50,
    )

    response = client.post(
        reverse("planner:toggle_rest_day", args=[today.isoformat()]),
        {"next": "today"},
    )

    assert response.status_code == 302
    assert response.url == reverse("planner:today")
    block.refresh_from_db()
    assert block.status == StudyBlock.Status.PENDING
    assert block.date == today
    assert RestDay.objects.filter(date=today).exists()

    rest_response = client.get(reverse("planner:today"))
    assert rest_response.context["rest_day"] is True
    assert rest_response.context["study_blocks"] == []
    rest_html = rest_response.content.decode()
    assert 'data-testid="rest-day-empty"' in rest_html
    assert "Your planned work stays saved (1 block)" in rest_html
    assert "Solve one array problem" not in rest_html

    client.post(
        reverse("planner:toggle_rest_day", args=[today.isoformat()]),
        {"next": "today"},
    )
    resumed_response = client.get(reverse("planner:today"))

    assert resumed_response.context["rest_day"] is False
    assert resumed_response.context["study_blocks"][0].pk == block.pk
    assert 'data-testid="study-block-title">Solve one array problem<' in (
        resumed_response.content.decode()
    )


@pytest.mark.django_db
def test_weekly_rest_day_action_hides_day_items_without_deleting_routine(
    client,
    current_week_start,
):
    generate_weekly_routine(current_week_start)
    rest_date = current_week_start + timedelta(days=1)

    client.post(
        reverse("planner:toggle_rest_day", args=[rest_date.isoformat()]),
    )
    response = client.get(reverse("planner:weekly_plan"))

    rest_day = response.context["days"][1]
    assert rest_day["is_rest_day"] is True
    assert rest_day["items"] == []
    assert rest_day["suppressed_block_count"] == 6
    assert StudyBlock.objects.filter(
        week_start=current_week_start,
        date=rest_date,
    ).count() == 6
    assert 'data-testid="weekly-rest-day"' in response.content.decode()

    client.post(
        reverse("planner:toggle_rest_day", args=[rest_date.isoformat()]),
    )
    reloaded = client.get(reverse("planner:weekly_plan"))

    assert reloaded.context["days"][1]["is_rest_day"] is False
    assert len(reloaded.context["days"][1]["items"]) == 6


@pytest.mark.django_db
def test_toggle_rest_day_service_is_reversible():
    day = timezone.localdate()

    assert toggle_rest_day(day) is True
    assert toggle_rest_day(day) is False
    assert not RestDay.objects.filter(date=day).exists()
