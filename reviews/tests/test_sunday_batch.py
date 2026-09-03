from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from problems.models import Problem

from reviews.models import ProblemReview, ProblemReviewEvent, ReviewRating
from reviews.services import (
    SUNDAY_REVIEW_DEFAULT_COUNT,
    sunday_review_batch,
)


NOW = datetime(2026, 9, 6, 12, 0, tzinfo=dt_timezone.utc)


def make_problem(number):
    return Problem.objects.create(
        title=f"Sunday Problem {number}",
        slug=f"sunday-problem-{number}",
        statement=f"Solve Sunday Problem {number}.",
        difficulty=Problem.Difficulty.EASY,
        source_name="Fixture",
        source_problem_id=str(number),
    )


def make_review(number, *, due_at):
    problem = make_problem(number)
    return ProblemReview.objects.create(
        problem=problem,
        rating=ReviewRating.SOLVED_WITH_HELP,
        interval_days=3,
        due_at=due_at,
    )


@pytest.mark.django_db
def test_sunday_batch_defaults_to_five_oldest_due_reviews():
    reviews = [
        make_review(number, due_at=NOW - timedelta(days=number))
        for number in range(1, 8)
    ]

    batch = list(sunday_review_batch(now=NOW))

    assert SUNDAY_REVIEW_DEFAULT_COUNT == 5
    assert len(batch) == SUNDAY_REVIEW_DEFAULT_COUNT
    assert [review.pk for review in batch] == [review.pk for review in reviews[::-1]][:5]


@pytest.mark.django_db
def test_sunday_batch_accepts_custom_count_and_rejects_non_positive_counts():
    reviews = [
        make_review(number, due_at=NOW - timedelta(days=number))
        for number in range(1, 5)
    ]

    batch = list(sunday_review_batch(count=2, now=NOW))

    assert [review.pk for review in batch] == [review.pk for review in reviews[::-1]][:2]
    with pytest.raises(ValidationError):
        sunday_review_batch(count=0, now=NOW)


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="reviews.tests.urls")
def test_sunday_batch_page_renders_custom_count_order_and_empty_state(client):
    now = timezone.now()
    make_review(1, due_at=now - timedelta(days=1))
    make_review(2, due_at=now - timedelta(days=2))
    make_review(3, due_at=now - timedelta(days=3))

    response = client.get(reverse("reviews:sunday_batch"), {"count": 2})

    assert response.status_code == 200
    assert response.context["batch_count"] == 2
    body = response.content.decode()
    assert body.count('data-testid="sunday-review-item"') == 2
    assert body.index("Sunday Problem 3") < body.index("Sunday Problem 2")
    assert "Sunday Problem 1" not in body
    assert 'data-testid="sunday-count-form"' in body

    ProblemReview.objects.all().delete()
    empty_response = client.get(reverse("reviews:sunday_batch"))

    assert 'data-testid="sunday-review-empty"' in empty_response.content.decode()
    assert "No due Problems in this batch." in empty_response.content.decode()


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="reviews.tests.urls")
def test_completing_one_sunday_review_refreshes_the_remaining_batch(client):
    now = timezone.now()
    completed = make_review(1, due_at=now - timedelta(days=2))
    remaining = make_review(2, due_at=now - timedelta(days=1))
    url = reverse("reviews:sunday_batch")

    response = client.post(
        url,
        data={
            "problem": completed.problem.slug,
            "count": 2,
            "rating": ReviewRating.SOLVED_INDEPENDENTLY,
            "note": "Rebuilt the invariant without help.",
        },
    )

    assert response.status_code == 302
    assert response["Location"].endswith("/reviews/sunday/?count=2&saved=1")
    completed.refresh_from_db()
    assert completed.rating == ReviewRating.SOLVED_INDEPENDENTLY
    assert completed.due_at > NOW
    assert ProblemReviewEvent.objects.filter(
        review=completed,
        rating=ReviewRating.SOLVED_INDEPENDENTLY,
        note="Rebuilt the invariant without help.",
    ).exists()

    refreshed = client.get(response["Location"])
    body = refreshed.content.decode()
    assert refreshed.context["batch_count"] == 2
    assert 'data-testid="sunday-review-saved"' in body
    assert body.count('data-testid="sunday-review-item"') == 1
    assert remaining.problem.title in body
    assert completed.problem.title not in body


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="reviews.tests.urls")
def test_sunday_today_page_exposes_the_batch_entrypoint(client):
    with patch("planner.views.timezone.localdate", return_value=NOW.date()):
        response = client.get(reverse("planner:today"))

    assert response.status_code == 200
    assert response.context["is_sunday"] is True
    body = response.content.decode()
    assert 'data-testid="sunday-review-entrypoint"' in body
    assert 'href="/reviews/sunday/"' in body
