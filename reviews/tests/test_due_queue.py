from datetime import timedelta
from unittest.mock import patch

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from planner.models import StudyBlock
from practice.models import LearningStatus, ProblemLearningStatus
from problems.models import Problem

from reviews.models import ProblemReview, ReviewRating
from reviews.services import due_review_queue


def make_problem(*, title, slug, is_active=True):
    return Problem.objects.create(
        title=title,
        slug=slug,
        statement=f"Solve {title}.",
        difficulty=Problem.Difficulty.EASY,
        source_name="LeetCode",
        source_problem_id=slug,
        is_active=is_active,
    )


def make_review(problem, *, due_at):
    return ProblemReview.objects.create(
        problem=problem,
        rating=ReviewRating.SOLVED_WITH_HELP,
        interval_days=3,
        due_at=due_at,
    )


@pytest.mark.django_db
def test_due_review_queue_is_stable_and_excludes_future_and_inactive_reviews():
    now = timezone.now()
    oldest = make_problem(title="Zebra", slug="zebra")
    same_time_first_alphabetically = make_problem(title="Alpha", slug="alpha")
    same_time_second_alphabetically = make_problem(title="Beta", slug="beta")
    future = make_problem(title="Future", slug="future")
    inactive = make_problem(title="Inactive", slug="inactive", is_active=False)

    make_review(oldest, due_at=now - timedelta(days=4))
    same_due_at = now - timedelta(hours=1)
    make_review(same_time_second_alphabetically, due_at=same_due_at)
    make_review(same_time_first_alphabetically, due_at=same_due_at)
    make_review(future, due_at=now + timedelta(days=1))
    make_review(inactive, due_at=now - timedelta(days=1))

    queued = list(due_review_queue(now=now))

    assert [review.problem.title for review in queued] == ["Zebra", "Alpha", "Beta"]
    assert all(review.due_at <= now for review in queued)
    assert {review.problem.title for review in queued}.isdisjoint({"Future", "Inactive"})
    assert list(due_review_queue(now=now).values_list("pk", flat=True)) == [
        review.pk for review in queued
    ]


@pytest.mark.django_db
def test_due_review_labels_distinguish_overdue_from_due_today():
    now = timezone.now()
    overdue_problem = make_problem(title="Old Queue Item", slug="old-queue-item")
    today_problem = make_problem(title="Today Queue Item", slug="today-queue-item")
    make_review(overdue_problem, due_at=now - timedelta(days=2))
    today_review = make_review(today_problem, due_at=now - timedelta(minutes=2))

    assert ProblemReview.objects.get(problem=overdue_problem).queue_due_label == "Overdue"
    assert today_review.queue_due_label == "Due today"


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="reviews.tests.urls")
def test_due_queue_route_renders_actions_statuses_and_empty_state(client):
    now = timezone.now()
    with_status = make_problem(title="Status Queue Item", slug="status-queue-item")
    without_status = make_problem(title="Unseen Queue Item", slug="unseen-queue-item")
    make_review(with_status, due_at=now - timedelta(days=1))
    make_review(without_status, due_at=now - timedelta(minutes=1))
    ProblemLearningStatus.objects.create(
        problem=with_status,
        status=LearningStatus.SOLVED_WITH_HELP,
        reason="Needed a hint.",
    )

    response = client.get(reverse("reviews:due_queue"))

    assert response.status_code == 200
    body = response.content.decode()
    assert body.count('data-testid="due-review-item"') == 2
    assert 'data-testid="due-review-link" href="/reviews/status-queue-item/"' in body
    assert 'data-testid="due-review-link" href="/reviews/unseen-queue-item/"' in body
    assert "Solved with help" in body
    assert "Unseen" in body
    assert body.index("Status Queue Item") < body.index("Unseen Queue Item")

    ProblemReview.objects.all().delete()
    empty_response = client.get(reverse("reviews:due_queue"))
    assert 'data-testid="due-review-empty"' in empty_response.content.decode()
    assert "Nothing is due today." in empty_response.content.decode()


@pytest.mark.django_db
def test_today_shows_due_reviews_on_weekdays_with_review_action_and_status(client):
    today = timezone.localdate()
    if today.weekday() >= 5:
        today = today - timedelta(days=today.weekday() - 4)
    problem = make_problem(title="Today Due Item", slug="today-due-item")
    make_review(problem, due_at=timezone.now() - timedelta(days=1))
    ProblemLearningStatus.objects.create(
        problem=problem,
        status=LearningStatus.ATTEMPTED,
        reason="Could not recall the invariant.",
    )
    StudyBlock.objects.create(date=today, title="Review", planned_minutes=20)

    with patch("planner.views.timezone.localdate", return_value=today):
        response = client.get(reverse("planner:today"))

    assert response.status_code == 200
    body = response.content.decode()
    assert response.context["is_weekday"] is True
    assert response.context["due_reviews"][0].problem_id == problem.pk
    assert 'data-testid="today-review-queue"' in body
    assert 'data-testid="today-due-review"' in body
    assert 'data-testid="review-action" href="/reviews/today-due-item/"' in body
    assert "Attempted" in body
    assert "couldn&#x27;t solve yet" in body


@pytest.mark.django_db
def test_today_hides_weekday_review_queue_on_weekends(client):
    saturday = timezone.localdate()
    saturday += timedelta(days=(5 - saturday.weekday()) % 7)
    problem = make_problem(title="Weekend Due Item", slug="weekend-due-item")
    make_review(problem, due_at=timezone.now() - timedelta(days=1))

    with patch("planner.views.timezone.localdate", return_value=saturday):
        response = client.get(reverse("planner:today"))

    assert response.status_code == 200
    assert response.context["is_weekday"] is False
    assert response.context["due_reviews"] == []
    assert 'data-testid="today-review-queue"' not in response.content.decode()
