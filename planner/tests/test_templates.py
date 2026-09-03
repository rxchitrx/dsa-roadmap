from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from planner.models import StudyBlock
from planner.services import generate_weekly_routine, week_start_for
from practice.models import LearningStatus, ProblemLearningStatus
from problems.models import Problem
from reviews.models import ProblemReview, ReviewRating


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


@pytest.mark.django_db
def test_today_ui_prioritizes_one_step_and_exposes_week_calendar(client):
    today = timezone.localdate()
    StudyBlock.objects.create(
        date=today,
        title="First focused step",
        planned_minutes=20,
    )
    StudyBlock.objects.create(
        date=today,
        title="Later focused step",
        planned_minutes=30,
    )

    response = client.get(reverse("planner:today"))
    html = response.content.decode()

    assert response.context["next_step_block"].title == "First focused step"
    assert html.count('data-testid="calendar-day"') == 7
    assert 'data-testid="curriculum-link"' in html
    assert "Planning navigation" not in html
    assert "Up next, in order" in html
    assert 'data-testid="up-next-step"' in html


@pytest.mark.django_db
def test_today_ui_can_open_a_selected_calendar_date(client):
    selected_date = timezone.localdate() + timedelta(days=1)
    StudyBlock.objects.create(
        date=selected_date,
        title="A future planned step",
        planned_minutes=25,
    )

    response = client.get(
        reverse("planner:today"),
        {"date": selected_date.isoformat()},
    )

    assert response.status_code == 200
    assert response.context["today"] == selected_date
    assert "A future planned step" in response.content.decode()


def test_today_ui_rejects_an_invalid_calendar_date(client):
    response = client.get(reverse("planner:today"), {"date": "not-a-date"})

    assert response.status_code == 400


@pytest.mark.django_db
def test_today_skips_revisit_when_no_review_is_due(client):
    today = timezone.localdate()
    problem = Problem.objects.create(
        title="Existing practice problem",
        slug="existing-practice-problem",
        statement="A saved practice problem.",
    )
    ProblemLearningStatus.objects.create(
        problem=problem,
        status=LearningStatus.ATTEMPTED,
    )
    generate_weekly_routine(week_start_for(today))

    response = client.get(reverse("planner:today"))

    assert response.context["next_step_block"].routine_key == f"{today.weekday()}-concept"
    assert response.context["deferred_review_block"] is not None
    assert 'data-testid="deferred-review-note"' in response.content.decode()


@pytest.mark.django_db
def test_today_leads_with_a_specific_due_review_when_one_exists(client):
    today = timezone.localdate()
    problem = Problem.objects.create(
        title="Review this exact problem",
        slug="review-this-exact-problem",
        statement="A saved review problem.",
    )
    now = timezone.now()
    ProblemReview.objects.create(
        problem=problem,
        rating=ReviewRating.SOLVED_WITH_HELP,
        interval_days=3,
        due_at=now - timedelta(hours=1),
        review_count=1,
        last_reviewed_at=now - timedelta(days=3),
    )
    generate_weekly_routine(week_start_for(today))

    response = client.get(reverse("planner:today"))
    html = response.content.decode()

    assert response.context["is_next_step_review"] is True
    assert response.context["next_step_block"].routine_key == f"{today.weekday()}-review"
    assert 'data-testid="next-due-review"' in html
    assert "Review this exact problem" in html
