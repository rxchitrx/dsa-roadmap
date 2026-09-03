from datetime import datetime, timedelta, timezone as dt_timezone

import pytest
from django.core.exceptions import ValidationError
from django.test import override_settings
from django.urls import reverse

from curriculum.models import Concept, Topic
from practice.models import LearningStatus, LearningStatusEvent, ProblemLearningStatus
from problems.models import Problem

from reviews.models import ProblemReview, ProblemReviewEvent, ReviewRating
from reviews.services import calculate_schedule, record_review


@pytest.fixture
def problem(db):
    topic = Topic.objects.create(
        name="Arrays & Strings",
        slug="arrays-strings",
        description="Foundations",
        display_order=1,
    )
    concept = Concept.objects.create(
        topic=topic,
        name="Array Fundamentals",
        slug="array-fundamentals",
        order=1,
        summary="Scan and remember arrays.",
        intuition="Keep a useful invariant.",
        explanation="Track the state as you scan.",
        complexity_notes="O(n)",
        implementation_guidance="Keep the invariant visible.",
        common_traps="Off-by-one errors.",
        guided_practice="Trace a small input.",
        checkpoint="Explain the invariant.",
    )
    return Problem.objects.create(
        concept=concept,
        title="Contains Duplicate",
        slug="contains-duplicate-review",
        statement="Return whether an array contains a duplicate.",
        difficulty=Problem.Difficulty.EASY,
        source_name="LeetCode",
        source_problem_id="217",
    )


def at_noon():
    return datetime(2026, 9, 3, 12, 0, tzinfo=dt_timezone.utc)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("rating", "interval_days"),
    [
        (ReviewRating.COULD_NOT_SOLVE, 1),
        (ReviewRating.SOLVED_WITH_HELP, 3),
        (ReviewRating.SOLVED_INDEPENDENTLY, 7),
    ],
)
def test_first_rating_creates_distinct_schedule_and_status_history(
    problem, rating, interval_days
):
    review, event = record_review(problem, rating=rating, reviewed_at=at_noon())

    assert review.pk is not None
    assert review.rating == rating
    assert review.interval_days == interval_days
    assert review.review_count == 1
    assert review.due_at == at_noon() + timedelta(days=interval_days)
    assert event.review_id == review.pk
    assert event.previous_rating == ""
    assert event.previous_interval_days == 0
    assert event.learning_status_event_id is not None
    assert LearningStatusEvent.objects.count() == 1

    status = ProblemLearningStatus.objects.get(problem=problem)
    expected_status = {
        ReviewRating.COULD_NOT_SOLVE: LearningStatus.ATTEMPTED,
        ReviewRating.SOLVED_WITH_HELP: LearningStatus.SOLVED_WITH_HELP,
        ReviewRating.SOLVED_INDEPENDENTLY: LearningStatus.SOLVED_INDEPENDENTLY,
    }[rating]
    assert status.status == expected_status


@pytest.mark.django_db
def test_first_rating_due_dates_and_intervals_are_distinct(problem):
    schedules = {
        rating: calculate_schedule(rating, reviewed_at=at_noon())
        for rating, _label in ReviewRating.choices
    }

    assert {schedule.interval_days for schedule in schedules.values()} == {1, 3, 7}
    assert len({schedule.due_at for schedule in schedules.values()}) == 3


@pytest.mark.django_db
def test_re_rating_updates_same_review_and_preserves_append_only_history(problem):
    first_review, first_event = record_review(
        problem,
        rating=ReviewRating.SOLVED_WITH_HELP,
        note="Needed a hint for the invariant.",
        reviewed_at=at_noon(),
    )
    second_review, second_event = record_review(
        problem,
        rating=ReviewRating.SOLVED_INDEPENDENTLY,
        note="Rebuilt the invariant without looking.",
        reviewed_at=at_noon() + timedelta(days=3),
    )

    assert second_review.pk == first_review.pk
    assert second_review.review_count == 2
    assert second_review.rating == ReviewRating.SOLVED_INDEPENDENTLY
    assert second_review.interval_days == 7
    assert second_review.due_at == at_noon() + timedelta(days=10)
    assert second_event.previous_rating == ReviewRating.SOLVED_WITH_HELP
    assert second_event.previous_interval_days == 3
    assert second_event.note.startswith("Rebuilt")
    assert [event.pk for event in second_review.history.order_by("reviewed_at", "pk")] == [
        first_event.pk,
        second_event.pk,
    ]


@pytest.mark.django_db
def test_could_not_solve_resets_a_long_interval_and_help_grows_it(problem):
    review, _event = record_review(
        problem,
        rating=ReviewRating.SOLVED_INDEPENDENTLY,
        reviewed_at=at_noon(),
    )
    assert review.interval_days == 7

    retry, retry_event = record_review(
        problem,
        rating=ReviewRating.COULD_NOT_SOLVE,
        reviewed_at=at_noon() + timedelta(days=7),
    )
    assert retry.pk == review.pk
    assert retry.interval_days == 1
    assert retry_event.previous_interval_days == 7

    helped, helped_event = record_review(
        problem,
        rating=ReviewRating.SOLVED_WITH_HELP,
        reviewed_at=at_noon() + timedelta(days=8),
    )
    assert helped.interval_days == 3
    assert helped_event.previous_interval_days == 1
    assert helped.review_count == 3


@pytest.mark.django_db
def test_invalid_rating_writes_nothing(problem):
    with pytest.raises(ValidationError):
        record_review(problem, rating="mastered", reviewed_at=at_noon())

    assert not ProblemReview.objects.exists()
    assert not ProblemReviewEvent.objects.exists()
    assert not LearningStatusEvent.objects.exists()


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="reviews.tests.urls")
def test_review_page_exposes_three_quick_rating_actions_and_empty_state(client, problem):
    response = client.get(reverse("reviews:problem_review", kwargs={"slug": problem.slug}))

    assert response.status_code == 200
    body = response.content.decode()
    assert 'data-testid="review-rating-form"' in body
    assert 'data-testid="rating-could_not_solve"' in body
    assert 'data-testid="rating-solved_with_help"' in body
    assert 'data-testid="rating-solved_independently"' in body
    assert 'data-testid="current-review-empty"' in body
    assert 'data-testid="review-history-empty"' in body


@pytest.mark.django_db
@pytest.mark.parametrize("rating", [value for value, _label in ReviewRating.choices])
@override_settings(ROOT_URLCONF="reviews.tests.urls")
def test_review_page_saves_each_rating_and_renders_due_state(client, problem, rating):
    response = client.post(
        reverse("reviews:problem_review", kwargs={"slug": problem.slug}),
        data={"rating": rating, "note": "A useful recall note."},
    )

    assert response.status_code == 302
    assert response["Location"].endswith(
        f"/reviews/{problem.slug}/?saved=1"
    )
    review = ProblemReview.objects.get(problem=problem)
    assert review.rating == rating
    assert review.due_at is not None

    page = client.get(response["Location"])
    assert page.status_code == 200
    body = page.content.decode()
    assert 'data-testid="review-saved"' in body
    assert 'data-testid="current-review-state"' in body
    assert 'data-testid="review-history-event"' in body
    assert "A useful recall note." in body


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="reviews.tests.urls")
def test_review_page_repeat_rating_keeps_one_schedule_and_two_history_rows(client, problem):
    url = reverse("reviews:problem_review", kwargs={"slug": problem.slug})
    client.post(url, data={"rating": ReviewRating.COULD_NOT_SOLVE})
    first_pk = ProblemReview.objects.get(problem=problem).pk

    client.post(url, data={"rating": ReviewRating.SOLVED_INDEPENDENTLY})

    review = ProblemReview.objects.get(problem=problem)
    assert review.pk == first_pk
    assert review.review_count == 2
    assert review.history.count() == 2
    assert review.history.filter(
        rating=ReviewRating.COULD_NOT_SOLVE
    ).exists()
    assert review.history.filter(
        rating=ReviewRating.SOLVED_INDEPENDENTLY
    ).exists()

    page = client.get(url)
    assert page.content.decode().count('data-testid="review-history-event"') == 2
