from datetime import date
import json

from django.core.files.uploadedfile import SimpleUploadedFile

import pytest
from django.urls import reverse

from planner.models import StudyBlock
from planner.backup import export_backup_json


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
def test_weekly_csv_route_downloads_the_selected_week(client):
    response = client.get(
        reverse("planner:weekly_csv_export"),
        {"week": "2026-09-02"},
    )

    assert response.status_code == 200
    assert response["Content-Type"] == "text/csv; charset=utf-8"
    assert response["Content-Disposition"] == (
        'attachment; filename="dsa-roadmap-week-2026-08-31.csv"'
    )
    assert response.content.startswith(b"record_type,week_start")


@pytest.mark.django_db
def test_weekly_csv_route_rejects_invalid_week_date(client):
    response = client.get(
        reverse("planner:weekly_csv_export"),
        {"week": "not-a-date"},
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_backup_routes_download_and_restore_with_validation(client, tmp_path, settings):
    original = StudyBlock.objects.create(
        date=date(2026, 9, 14),
        week_start=date(2026, 9, 14),
        routine_key="0-review",
        title="Original review",
        planned_minutes=20,
    )
    backup = export_backup_json()
    StudyBlock.objects.create(
        date=date(2026, 9, 14),
        week_start=date(2026, 9, 14),
        routine_key="0-concept",
        title="Extra block",
        planned_minutes=30,
    )
    settings.DSA_BACKUP_DIR = tmp_path

    page = client.get(reverse("planner:backup_center"))
    assert page.status_code == 200
    assert 'data-testid="backup-center"' in page.content.decode()

    download = client.get(reverse("planner:backup_export"))
    assert download.status_code == 200
    assert download["Content-Type"] == "application/json; charset=utf-8"
    assert json.loads(download.content)["format"] == "dsa-roadmap-backup"

    restored = client.post(
        reverse("planner:backup_restore"),
        {"backup": SimpleUploadedFile("journey.json", backup.encode(), content_type="application/json")},
    )
    assert restored.status_code == 200
    assert 'data-testid="backup-restored"' in restored.content.decode()
    assert list(StudyBlock.objects.values_list("title", flat=True)) == [original.title]
    assert list(tmp_path.glob("safety-*.json"))


@pytest.mark.django_db
def test_backup_restore_route_keeps_data_on_invalid_upload(client):
    block = StudyBlock.objects.create(
        date=date(2026, 9, 14),
        title="Keep me",
        planned_minutes=20,
    )

    response = client.post(
        reverse("planner:backup_restore"),
        {"backup": SimpleUploadedFile("bad.json", b'{"version": 2}', content_type="application/json")},
    )

    assert response.status_code == 400
    assert 'data-testid="backup-error"' in response.content.decode()
    assert StudyBlock.objects.filter(pk=block.pk, title="Keep me").exists()


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
