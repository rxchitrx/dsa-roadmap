from datetime import date

import pytest
from django.urls import reverse

from planner.models import StudyBlock


@pytest.mark.django_db
def test_progress_analytics_route_renders_empty_evidence_and_accepts_date_range(client):
    response = client.get(
        reverse("planner:progress_analytics"),
        {"start": "2026-09-01", "end": "2026-09-07"},
    )

    assert response.status_code == 200
    assert response.context["analytics"]["range"] == {
        "start_date": date(2026, 9, 1),
        "end_date": date(2026, 9, 7),
        "days": 7,
    }
    body = response.content.decode()
    assert 'data-testid="progress-analytics"' in body
    assert 'data-testid="analytics-missing-data"' in body
    assert "No learning activity" in body


@pytest.mark.django_db
def test_progress_analytics_route_rejects_invalid_dates(client):
    response = client.get(
        reverse("planner:progress_analytics"),
        {"start": "2026-09-08", "end": "2026-09-01"},
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_next_week_plan_route_previews_and_saves_editable_blocks(client):
    preview = client.get(
        reverse("planner:next_week_plan"),
        {"week": "2026-09-14"},
    )

    assert preview.status_code == 200
    assert preview.context["plan"].week_start == date(2026, 9, 14)
    assert len(preview.context["plan"].blocks) == 37
    assert 'data-testid="next-week-plan"' in preview.content.decode()

    saved = client.post(
        reverse("planner:save_next_week_plan"),
        {
            "week": "2026-09-14",
            "block__0-review__title": "Revisit a hard one",
            "block__0-review__planned_minutes": "25",
            "block__0-review__date": "2026-09-14",
        },
    )

    assert saved.status_code == 200
    assert 'data-testid="plan-saved"' in saved.content.decode()
    block = StudyBlock.objects.get(
        week_start=date(2026, 9, 14),
        routine_key="0-review",
    )
    assert block.title == "Revisit a hard one"
    assert block.planned_minutes == 25


@pytest.mark.django_db
def test_next_week_plan_route_rejects_bad_week_date(client):
    response = client.get(
        reverse("planner:next_week_plan"),
        {"week": "not-a-date"},
    )

    assert response.status_code == 400
