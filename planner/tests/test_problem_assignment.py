from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from curriculum.models import Concept, Topic
from planner.models import StudyBlock, StudyBlockProblem
from planner.services import (
    assign_weekday_problems,
    generate_weekly_routine,
    set_manual_problem_assignments,
    week_start_for,
)
from practice.models import LearningStatus, ProblemLearningStatus
from problems.models import Problem
from reviews.models import ProblemReview, ReviewRating


def make_concept(name="Arrays", *, suffix="1"):
    topic = Topic.objects.create(
        name=f"{name} topic {suffix}",
        slug=f"{name.lower().replace(' ', '-')}-topic-{suffix}",
        description="A DSA topic for planner assignment tests.",
        display_order=int(suffix) if suffix.isdigit() else 1,
    )
    return Concept.objects.create(
        topic=topic,
        name=name,
        slug=f"{name.lower().replace(' ', '-')}-{suffix}",
        order=1,
        summary="A focused concept.",
        intuition="Build the right mental model.",
        explanation="Use the concept deliberately.",
        examples=[],
        complexity_notes="Keep the complexity visible.",
        implementation_guidance="Implement the invariant.",
        common_traps="Do not skip the edge cases.",
        guided_practice="Trace one example.",
        checkpoint="Explain the idea from memory.",
    )


def make_problem(concept, title, *, display_order=1):
    return Problem.objects.create(
        concept=concept,
        title=title,
        slug=title.lower().replace(" ", "-"),
        statement="Solve this DSA problem.",
        difficulty=Problem.Difficulty.EASY,
        source_name="Test catalog",
        source_problem_id=title,
        display_order=display_order,
    )


def solve_blocks(week_start):
    return list(
        StudyBlock.objects.filter(
            week_start=week_start,
            date__range=(week_start, week_start + timedelta(days=4)),
            routine_key__endswith="-problems",
        ).order_by("date", "position", "id")
    )


@pytest.mark.django_db
def test_fills_each_weekday_solve_block_with_two_distinct_ready_problems():
    week_start = week_start_for(timezone.localdate())
    concept = make_concept()
    problems = [
        make_problem(concept, f"Problem {index}", display_order=index)
        for index in range(1, 11)
    ]

    generate_weekly_routine(week_start)

    blocks = solve_blocks(week_start)
    assert len(blocks) == 5
    assert all(block.problem_assignments.count() == 2 for block in blocks)
    assert all(
        block.problem_assignments.values_list("problem_id", flat=True).distinct().count()
        == 2
        for block in blocks
    )
    assert (
        StudyBlockProblem.objects.filter(study_block__in=blocks).count() == len(problems)
    )


@pytest.mark.django_db
def test_learning_status_prioritizes_help_needed_and_skips_mastered_problems():
    week_start = week_start_for(timezone.localdate())
    concept = make_concept()
    attempted = make_problem(concept, "Attempted problem", display_order=10)
    helped = make_problem(concept, "Helped problem", display_order=20)
    unseen = make_problem(concept, "Unseen problem", display_order=1)
    mastered = make_problem(concept, "Mastered problem", display_order=0)
    ProblemLearningStatus.objects.create(
        problem=attempted,
        status=LearningStatus.ATTEMPTED,
    )
    ProblemLearningStatus.objects.create(
        problem=helped,
        status=LearningStatus.SOLVED_WITH_HELP,
    )
    ProblemLearningStatus.objects.create(
        problem=mastered,
        status=LearningStatus.SOLVED_INDEPENDENTLY,
    )
    generate_weekly_routine(week_start)

    first_block = solve_blocks(week_start)[0]
    assigned_ids = list(
        first_block.problem_assignments.values_list("problem_id", flat=True)
    )

    assert assigned_ids == [attempted.pk, helped.pk]
    assert mastered.pk not in StudyBlockProblem.objects.values_list(
        "problem_id", flat=True
    )
    assert unseen.pk not in assigned_ids


@pytest.mark.django_db
def test_due_review_reopens_an_independently_solved_problem_for_assignment():
    week_start = week_start_for(timezone.localdate())
    concept = make_concept()
    due_problem = make_problem(concept, "Due mastered problem", display_order=50)
    future_problem = make_problem(concept, "Future mastered problem", display_order=1)
    ProblemLearningStatus.objects.create(
        problem=due_problem,
        status=LearningStatus.SOLVED_INDEPENDENTLY,
    )
    ProblemLearningStatus.objects.create(
        problem=future_problem,
        status=LearningStatus.SOLVED_INDEPENDENTLY,
    )
    now = timezone.now()
    ProblemReview.objects.create(
        problem=due_problem,
        rating=ReviewRating.SOLVED_INDEPENDENTLY,
        due_at=now - timedelta(minutes=1),
    )
    ProblemReview.objects.create(
        problem=future_problem,
        rating=ReviewRating.SOLVED_INDEPENDENTLY,
        due_at=now + timedelta(days=3),
    )
    generate_weekly_routine(week_start)

    assigned_ids = set(
        StudyBlockProblem.objects.filter(study_block__week_start=week_start).values_list(
            "problem_id", flat=True
        )
    )

    assert due_problem.pk in assigned_ids
    assert future_problem.pk not in assigned_ids


@pytest.mark.django_db
def test_sparse_pool_assigns_only_available_problems():
    week_start = week_start_for(timezone.localdate())
    concept = make_concept()
    only_problem = make_problem(concept, "Only available problem")
    generate_weekly_routine(week_start)

    assignments = StudyBlockProblem.objects.filter(study_block__week_start=week_start)

    assert assignments.count() == 1
    assert assignments.get().problem_id == only_problem.pk
    assert all(block.problem_assignments.count() <= 2 for block in solve_blocks(week_start))


@pytest.mark.django_db
def test_repeated_assignment_is_idempotent_and_does_not_duplicate_weekly_problems():
    week_start = week_start_for(timezone.localdate())
    concept = make_concept()
    for index in range(1, 4):
        make_problem(concept, f"Repeat-safe problem {index}", display_order=index)
    generate_weekly_routine(week_start)
    first_ids = list(
        StudyBlockProblem.objects.order_by("study_block_id", "position", "id").values_list(
            "pk", flat=True
        )
    )

    assign_weekday_problems(week_start)
    second_ids = list(
        StudyBlockProblem.objects.order_by("study_block_id", "position", "id").values_list(
            "pk", flat=True
        )
    )

    assert second_ids == first_ids


@pytest.mark.django_db
def test_manual_assignments_are_preserved_and_fill_remaining_slot():
    week_start = week_start_for(timezone.localdate())
    concept = make_concept()
    manual = make_problem(concept, "Manual override", display_order=100)
    automatic = make_problem(concept, "Automatic follow-up", display_order=1)
    generate_weekly_routine(week_start)
    block = solve_blocks(week_start)[0]

    set_manual_problem_assignments(block, [manual])
    assign_weekday_problems(week_start)

    assignments = list(
        block.problem_assignments.order_by("position", "id").select_related("problem")
    )
    assert [assignment.problem_id for assignment in assignments] == [
        manual.pk,
        automatic.pk,
    ]
    assert assignments[0].assignment_source == StudyBlockProblem.AssignmentSource.MANUAL


@pytest.mark.django_db
def test_weekly_editor_can_set_a_manual_problem_override(client):
    week_start = week_start_for(timezone.localdate())
    concept = make_concept()
    first = make_problem(concept, "First choice")
    second = make_problem(concept, "Second choice")
    generate_weekly_routine(week_start)
    block = solve_blocks(week_start)[0]

    response = client.post(
        reverse("planner:edit_study_block", args=[block.pk]),
        {
            "title": block.title,
            "planned_minutes": block.planned_minutes,
            "manage_problems": "1",
            "assigned_problems": [str(first.pk), str(second.pk)],
        },
    )

    assert response.status_code == 302
    assignments = list(
        block.problem_assignments.order_by("position", "id").values_list(
            "problem_id", "assignment_source"
        )
    )
    assert assignments == [
        (first.pk, StudyBlockProblem.AssignmentSource.MANUAL),
        (second.pk, StudyBlockProblem.AssignmentSource.MANUAL),
    ]


@pytest.mark.django_db
def test_today_and_weekly_plan_render_problem_assignments(client):
    today = timezone.localdate()
    week_start = week_start_for(today)
    concept = make_concept()
    problem = make_problem(concept, "Visible assigned problem")
    generate_weekly_routine(week_start)

    today_block = StudyBlock.objects.get(date=today, routine_key=f"{today.weekday()}-problems")
    set_manual_problem_assignments(today_block, [problem])

    today_response = client.get(reverse("planner:today"))
    weekly_response = client.get(reverse("planner:weekly_plan"))

    assert 'data-testid="assigned-problems"' in today_response.content.decode()
    assert 'data-testid="assigned-problem"' in today_response.content.decode()
    assert "Visible assigned problem" in weekly_response.content.decode()
    assert reverse("problems:detail", args=[problem.slug]) in today_response.content.decode()
