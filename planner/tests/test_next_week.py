from datetime import date, datetime, timedelta, timezone as dt_timezone

import pytest

from curriculum.models import Concept, Topic
from planner.models import StudyBlock, StudyBlockProblem
from planner.next_week import (
    NextWeekPlanError,
    edit_next_week_plan,
    generate_next_week_plan,
    save_next_week_plan,
)
from practice.models import LearningStatus, ProblemLearningStatus
from problems.models import Problem
from reviews.models import ProblemReview, ReviewRating


REFERENCE_WEEK = date(2026, 9, 7)
TARGET_WEEK = date(2026, 9, 14)
NOW = datetime(2026, 9, 10, 12, tzinfo=dt_timezone.utc)


def make_concept(name="Arrays"):
    topic = Topic.objects.create(
        name=f"{name} topic",
        slug=f"{name.lower()}-topic",
        description="A focused DSA topic.",
        display_order=1,
    )
    return Concept.objects.create(
        topic=topic,
        name=name,
        slug=name.lower().replace(" ", "-"),
        order=1,
        summary="A focused concept.",
        intuition="Build the invariant first.",
        explanation="Use the concept deliberately.",
        examples=[],
        complexity_notes="Track time and space.",
        implementation_guidance="Implement the invariant.",
        common_traps="Check empty and boundary inputs.",
        guided_practice="Trace one example by hand.",
        checkpoint="Explain the idea from memory.",
    )


def make_problem(title, *, concept=None, display_order=1):
    return Problem.objects.create(
        concept=concept,
        title=title,
        slug=title.lower().replace(" ", "-"),
        statement="Solve this DSA Problem.",
        difficulty=Problem.Difficulty.EASY,
        source_name="Test catalog",
        source_problem_id=title,
        display_order=display_order,
    )


@pytest.mark.django_db
def test_preview_combines_inputs_without_writing_planner_rows():
    concept = make_concept()
    due_problem = make_problem("Due review", concept=concept)
    solve_problems = [
        make_problem(f"New Problem {index}", concept=concept, display_order=index)
        for index in range(1, 11)
    ]
    ProblemReview.objects.create(
        problem=due_problem,
        rating=ReviewRating.SOLVED_INDEPENDENTLY,
        due_at=NOW - timedelta(days=1),
    )
    unfinished = StudyBlock.objects.create(
        date=REFERENCE_WEEK + timedelta(days=2),
        week_start=REFERENCE_WEEK,
        routine_key="2-problems",
        title="Finish the old graph problem",
        planned_minutes=50,
    )

    plan = generate_next_week_plan(
        target_week_start=TARGET_WEEK,
        now=NOW,
    )

    assert plan.week_start == TARGET_WEEK
    assert StudyBlock.objects.filter(week_start=TARGET_WEEK).count() == 0
    assert unfinished.pk in plan.unfinished_block_ids
    assert any(block.source == "unfinished" for block in plan.blocks)
    assert plan.recommendation.concept_id == concept.pk

    review_blocks = [block for block in plan.blocks if block.block_type == "review"]
    assert review_blocks[0].problem_ids == (due_problem.pk,)
    assert due_problem.pk in plan.scheduled_due_review_ids
    assert due_problem.pk not in {
        problem_id
        for block in plan.blocks
        if block.block_type == "problems"
        for problem_id in block.problem_ids
    }

    assert any(block.block_type == "assessment" for block in plan.blocks)
    assert any(block.block_type == "planning" for block in plan.blocks)
    assert any(
        block.block_type == "problems" and block.problem_ids for block in plan.blocks
    )


@pytest.mark.django_db
def test_due_reviews_are_scheduled_oldest_first_and_not_duplicated():
    concept = make_concept()
    due_problems = [
        make_problem(f"Due {index}", concept=concept, display_order=index)
        for index in range(1, 9)
    ]
    for index, problem in enumerate(due_problems):
        ProblemReview.objects.create(
            problem=problem,
            rating=ReviewRating.COULD_NOT_SOLVE,
            due_at=NOW - timedelta(days=index + 1),
        )

    plan = generate_next_week_plan(target_week_start=TARGET_WEEK, now=NOW)
    scheduled_ids = [
        problem_id
        for block in plan.blocks
        for problem_id in block.problem_ids
        if problem_id in {problem.pk for problem in due_problems}
    ]

    expected_order = [problem.pk for problem in reversed(due_problems)]
    assert scheduled_ids == expected_order
    assert len(scheduled_ids) == len(set(scheduled_ids))
    assert plan.unscheduled_due_review_ids == ()
    sunday = plan.block_by_key["6-review-batch"]
    assert sunday.problem_ids == tuple(expected_order[5:])


@pytest.mark.django_db
def test_save_is_idempotent_and_preserves_completion_state():
    concept = make_concept()
    problem = make_problem("A practice problem", concept=concept)
    ProblemLearningStatus.objects.create(
        problem=problem,
        status=LearningStatus.ATTEMPTED,
    )

    plan = generate_next_week_plan(target_week_start=TARGET_WEEK, now=NOW)
    first_saved = save_next_week_plan(plan)
    first_block_ids = list(
        StudyBlock.objects.filter(week_start=TARGET_WEEK)
        .order_by("date", "position", "id")
        .values_list("id", flat=True)
    )
    first_assignment_count = StudyBlockProblem.objects.filter(
        study_block__week_start=TARGET_WEEK
    ).count()

    completed = StudyBlock.objects.get(
        week_start=TARGET_WEEK,
        routine_key="0-review",
    )
    completed.status = StudyBlock.Status.COMPLETED
    completed.save(update_fields=("status", "updated_at"))

    second_plan = generate_next_week_plan(target_week_start=TARGET_WEEK, now=NOW)
    second_saved = save_next_week_plan(second_plan)

    assert first_saved.week_start == second_saved.week_start == TARGET_WEEK
    assert list(
        StudyBlock.objects.filter(week_start=TARGET_WEEK)
        .order_by("date", "position", "id")
        .values_list("id", flat=True)
    ) == first_block_ids
    assert StudyBlock.objects.filter(week_start=TARGET_WEEK).count() == 37
    assert (
        StudyBlockProblem.objects.filter(
            study_block__week_start=TARGET_WEEK
        ).count()
        == first_assignment_count
    )
    completed.refresh_from_db()
    assert completed.status == StudyBlock.Status.COMPLETED


@pytest.mark.django_db
def test_edits_are_in_memory_until_save_and_then_persist():
    concept = make_concept()
    manual_problem = make_problem("Manually selected Problem")
    plan = generate_next_week_plan(target_week_start=TARGET_WEEK, now=NOW)
    edited = edit_next_week_plan(
        plan,
        {
            "0-concept": {
                "title": "Learn monotonic stacks",
                "planned_minutes": 45,
                "assigned_concept": concept.pk,
            },
            "0-review": {
                "title": "Re-solve the selected review",
                "problem_ids": [manual_problem.pk],
            },
        },
    )

    assert StudyBlock.objects.count() == 0
    assert edited.block_by_key["0-concept"].title == "Learn monotonic stacks"
    assert edited.block_by_key["0-concept"].planned_minutes == 45
    assert edited.block_by_key["0-concept"].concept_id == concept.pk

    save_next_week_plan(edited)

    saved_concept = StudyBlock.objects.get(
        week_start=TARGET_WEEK,
        routine_key="0-concept",
    )
    saved_review = StudyBlock.objects.get(
        week_start=TARGET_WEEK,
        routine_key="0-review",
    )
    assert saved_concept.title == "Learn monotonic stacks"
    assert saved_concept.planned_minutes == 45
    assert saved_concept.assigned_concept_id == concept.pk
    assert tuple(
        saved_review.problem_assignments.values_list("problem_id", flat=True)
    ) == (manual_problem.pk,)


@pytest.mark.django_db
def test_edits_reject_duplicate_assignments_and_invalid_week_dates():
    plan = generate_next_week_plan(target_week_start=TARGET_WEEK, now=NOW)
    problem = make_problem("Manual Problem")

    with pytest.raises(NextWeekPlanError, match="more than once"):
        edit_next_week_plan(
            plan,
            {
                "0-review": {"problem_ids": [problem.pk]},
                "1-review": {"problem_ids": [problem.pk]},
            },
        )

    with pytest.raises(NextWeekPlanError, match="inside the planned week"):
        edit_next_week_plan(
            plan,
            {
                "0-review": {
                    "date": TARGET_WEEK - timedelta(days=1),
                }
            },
        )
