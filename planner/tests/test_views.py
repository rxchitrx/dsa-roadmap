import pytest
from django.urls import reverse
from django.utils import timezone

from planner.models import StudyBlock


@pytest.mark.django_db
def test_today_renders_the_persisted_block_and_refresh_keeps_it(client):
    today = timezone.localdate()
    block = StudyBlock.objects.create(
        date=today,
        title="Re-solve an old question",
        planned_minutes=20,
    )

    first_response = client.get(reverse("planner:today"))
    refreshed_response = client.get(reverse("planner:today"))

    assert first_response.status_code == 200
    assert first_response.context["study_block"].pk == block.pk
    assert refreshed_response.context["study_block"].pk == block.pk
    assert first_response.context["today"] == today


@pytest.mark.django_db
def test_today_renders_an_empty_state_when_no_block_exists(client):
    response = client.get(reverse("planner:today"))

    assert response.status_code == 200
    assert response.context["study_block"] is None
    assert "Nothing planned for today." in response.content.decode()
