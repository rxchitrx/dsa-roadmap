import pytest
from django.urls import reverse
from django.utils import timezone

from planner.models import StudyBlock


@pytest.mark.django_db
def test_today_ui_shows_title_duration_and_pending_status(client):
    StudyBlock.objects.create(
        date=timezone.localdate(),
        title="Solve two sliding-window problems",
        planned_minutes=50,
    )

    response = client.get(reverse("planner:today"))
    html = response.content.decode()

    assert 'data-testid="study-block"' in html
    assert 'data-testid="study-block-title">Solve two sliding-window problems<' in html
    assert "50 min planned" in html
    assert 'data-testid="study-block-status"' in html
    assert "Pending" in html


@pytest.mark.django_db
def test_today_ui_shows_completed_status_for_completed_block(client):
    today = timezone.localdate()
    StudyBlock.objects.create(
        date=today,
        title="Rewrite the solution",
        planned_minutes=20,
        status=StudyBlock.Status.COMPLETED,
    )

    response = client.get(reverse("planner:today"))

    assert 'class="status status--completed"' in response.content.decode()
    assert "Completed" in response.content.decode()


@pytest.mark.django_db
def test_today_ui_shows_empty_state_without_a_study_block(client):
    response = client.get(reverse("planner:today"))

    html = response.content.decode()
    assert 'data-testid="today-empty"' in html
    assert "Nothing planned for today." in html
    assert 'data-testid="study-block"' not in html
