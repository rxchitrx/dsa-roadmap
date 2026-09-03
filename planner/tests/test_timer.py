from datetime import datetime, timedelta, timezone as dt_timezone

import pytest
from django.urls import reverse
from django.utils import timezone

from planner.models import StudyBlock, WorkSession
from planner.services import (
    ActiveWorkSessionError,
    pause_work_session,
    resume_work_session,
    start_work_session,
    stop_work_session,
)


def instant(hour, minute=0, second=0):
    return datetime(
        2026,
        9,
        3,
        hour,
        minute,
        second,
        tzinfo=dt_timezone.utc,
    )


@pytest.fixture
def study_block():
    return StudyBlock.objects.create(
        date=timezone.localdate(),
        title="Solve a graph problem",
        planned_minutes=50,
    )


@pytest.mark.django_db
def test_work_session_calculates_running_time_and_persists_pause(study_block):
    started_at = instant(9)
    session = start_work_session(study_block, started_at)

    assert session.status == WorkSession.Status.RUNNING
    assert session.elapsed_seconds == 0
    assert session.elapsed_seconds_at(started_at + timedelta(seconds=125)) == 125

    paused = pause_work_session(session, started_at + timedelta(seconds=125))
    paused.refresh_from_db()
    assert paused.status == WorkSession.Status.PAUSED
    assert paused.elapsed_seconds == 125
    assert paused.elapsed_seconds_at(started_at + timedelta(hours=1)) == 125


@pytest.mark.django_db
def test_work_session_resume_and_stop_accumulate_elapsed_time(study_block):
    started_at = instant(9)
    session = start_work_session(study_block, started_at)
    session = pause_work_session(session, started_at + timedelta(seconds=125))
    session = resume_work_session(session, started_at + timedelta(seconds=300))
    session = stop_work_session(session, started_at + timedelta(seconds=500))

    session.refresh_from_db()
    assert session.status == WorkSession.Status.STOPPED
    assert session.elapsed_seconds == 325
    assert session.stopped_at == started_at + timedelta(seconds=500)
    assert not session.is_active


@pytest.mark.django_db
def test_only_one_active_work_session_can_exist_per_study_block(study_block):
    start_work_session(study_block, instant(9))

    with pytest.raises(ActiveWorkSessionError):
        start_work_session(study_block, instant(10))

    assert WorkSession.objects.filter(study_block=study_block).count() == 1


@pytest.mark.django_db
def test_a_stopped_block_can_start_a_new_logged_session(study_block):
    first = start_work_session(study_block, instant(9))
    stop_work_session(first, instant(9, 5))

    second = start_work_session(study_block, instant(10))

    assert second.pk != first.pk
    assert second.status == WorkSession.Status.RUNNING
    assert WorkSession.objects.filter(study_block=study_block).count() == 2


@pytest.mark.django_db
def test_stopping_only_completes_the_block_when_explicitly_requested(study_block):
    first = start_work_session(study_block, instant(9))
    stop_work_session(first, instant(9, 5))
    study_block.refresh_from_db()
    assert study_block.status == StudyBlock.Status.PENDING

    second = start_work_session(study_block, instant(10))
    stop_work_session(second, instant(10, 5), complete_block=True)
    study_block.refresh_from_db()
    assert study_block.status == StudyBlock.Status.COMPLETED


@pytest.mark.django_db
def test_timer_routes_persist_start_pause_resume_and_refresh_state(client, study_block):
    start_response = client.post(
        reverse("planner:start_timer", args=[study_block.pk])
    )
    assert start_response.status_code == 302

    refreshed = client.get(reverse("planner:today"))
    html = refreshed.content.decode()
    assert 'data-testid="timer-panel"' in html
    assert 'data-status="running"' in html
    assert 'data-testid="pause-timer"' in html
    assert 'data-testid="stop-timer"' in html
    assert 'data-testid="start-timer"' not in html

    pause_response = client.post(
        reverse("planner:pause_timer", args=[study_block.pk])
    )
    assert pause_response.status_code == 302
    paused_html = client.get(reverse("planner:today")).content.decode()
    assert 'data-status="paused"' in paused_html
    assert 'data-testid="resume-timer"' in paused_html

    resume_response = client.post(
        reverse("planner:resume_timer", args=[study_block.pk])
    )
    assert resume_response.status_code == 302
    assert WorkSession.objects.get(study_block=study_block).status == (
        WorkSession.Status.RUNNING
    )


@pytest.mark.django_db
def test_duplicate_start_route_returns_actionable_conflict_without_new_session(
    client, study_block
):
    client.post(reverse("planner:start_timer", args=[study_block.pk]))

    response = client.post(
        reverse("planner:start_timer", args=[study_block.pk])
    )

    assert response.status_code == 409
    assert "already has an active timer" in response.content.decode()
    assert WorkSession.objects.filter(study_block=study_block).count() == 1


@pytest.mark.django_db
def test_stop_route_keeps_block_pending_without_checkbox(client, study_block):
    client.post(reverse("planner:start_timer", args=[study_block.pk]))

    response = client.post(reverse("planner:stop_timer", args=[study_block.pk]))

    assert response.status_code == 302
    study_block.refresh_from_db()
    session = WorkSession.objects.get(study_block=study_block)
    assert session.status == WorkSession.Status.STOPPED
    assert study_block.status == StudyBlock.Status.PENDING

    stopped_html = client.get(reverse("planner:today")).content.decode()
    assert 'data-status="stopped"' in stopped_html
    assert 'data-testid="start-timer"' in stopped_html


@pytest.mark.django_db
def test_stop_route_completes_block_only_with_explicit_checkbox(client, study_block):
    client.post(reverse("planner:start_timer", args=[study_block.pk]))

    response = client.post(
        reverse("planner:stop_timer", args=[study_block.pk]),
        {"complete_block": "1"},
    )

    assert response.status_code == 302
    study_block.refresh_from_db()
    assert study_block.status == StudyBlock.Status.COMPLETED
