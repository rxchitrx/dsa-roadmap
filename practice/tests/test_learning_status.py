import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from problems.models import Problem

from practice.models import (
    LearningStatus,
    LearningStatusEvent,
    PracticeRun,
    ProblemLearningStatus,
    SolutionReflection,
)
from practice.services import (
    get_or_create_learning_status,
    run_visible_tests,
    set_learning_status,
)


@pytest.fixture
def problem(db):
    return Problem.objects.create(
        title="Contains Duplicate",
        slug="contains-duplicate",
        statement="Return whether any value appears more than once.",
        difficulty=Problem.Difficulty.EASY,
        source_name="LeetCode",
        source_problem_id="217",
    )


@pytest.fixture
def other_problem(db):
    return Problem.objects.create(
        title="Other Problem",
        slug="other-problem",
        statement="Return a value.",
    )


def status_url(problem):
    return reverse(
        "practice:update_learning_status",
        kwargs={"slug": problem.slug},
    )


def status_payload(status=LearningStatus.ATTEMPTED, reason="I could not finish the trace yet."):
    return {"status": status, "reason": reason}


@pytest.mark.django_db
def test_new_problem_starts_unseen_without_creating_history(problem):
    learning_status = get_or_create_learning_status(problem)

    assert learning_status.status == LearningStatus.UNSEEN
    assert learning_status.reason == ""
    assert not LearningStatusEvent.objects.exists()


@pytest.mark.django_db
def test_status_transitions_update_current_state_and_preserve_every_event(problem):
    first_status, first_event = set_learning_status(
        problem,
        status=LearningStatus.ATTEMPTED,
        reason="I understood the idea but could not complete the edge-case trace.",
    )
    second_status, second_event = set_learning_status(
        problem,
        status=LearningStatus.SOLVED_WITH_HELP,
        reason="I used one hint, then rewrote the invariant in my own words.",
    )

    current = ProblemLearningStatus.objects.get(problem=problem)
    events = list(
        LearningStatusEvent.objects.filter(learning_status=current).order_by(
            "changed_at", "id"
        )
    )

    assert first_status.pk == second_status.pk == current.pk
    assert current.status == LearningStatus.SOLVED_WITH_HELP
    assert current.reason == second_event.reason
    assert [event.status for event in events] == [
        LearningStatus.ATTEMPTED,
        LearningStatus.SOLVED_WITH_HELP,
    ]
    assert [event.reason for event in events] == [
        first_event.reason,
        second_event.reason,
    ]
    assert first_event.changed_at <= second_event.changed_at
    assert first_event.problem_snapshot.version == 1
    assert second_event.problem_snapshot_id == first_event.problem_snapshot_id


@pytest.mark.django_db
def test_repeating_a_status_still_records_new_reason_and_timestamp(problem):
    first_status, first_event = set_learning_status(
        problem,
        status=LearningStatus.ATTEMPTED,
        reason="The first attempt stopped at the invariant.",
    )
    _, second_event = set_learning_status(
        problem,
        status=LearningStatus.ATTEMPTED,
        reason="I can now trace the invariant, but still need another recall pass.",
    )

    assert first_status.pk == second_event.learning_status_id
    assert LearningStatusEvent.objects.filter(
        learning_status=first_status
    ).count() == 2
    assert second_event.changed_at >= first_event.changed_at
    assert ProblemLearningStatus.objects.get(pk=first_status.pk).reason == (
        "I can now trace the invariant, but still need another recall pass."
    )


@pytest.mark.django_db
def test_status_reason_and_status_value_are_validated_before_writing(problem):
    with pytest.raises(ValidationError):
        set_learning_status(problem, status="mastered", reason="Not a valid state.")
    with pytest.raises(ValidationError):
        set_learning_status(problem, status=LearningStatus.ATTEMPTED, reason="  ")

    assert not ProblemLearningStatus.objects.exists()
    assert not LearningStatusEvent.objects.exists()


@pytest.mark.django_db
def test_passing_execution_does_not_change_learning_status(problem):
    run = run_visible_tests(
        problem,
        code="def contains_duplicate(nums):\n    return len(nums) != len(set(nums))\n",
    )

    learning_status = get_or_create_learning_status(problem)

    assert run.status == PracticeRun.Status.PASSED
    assert learning_status.status == LearningStatus.UNSEEN
    assert not LearningStatusEvent.objects.exists()


@pytest.mark.django_db
def test_status_event_can_keep_run_reflection_and_snapshot_evidence(problem):
    run = PracticeRun.objects.create(
        problem=problem,
        code="def contains_duplicate(nums):\n    return True\n",
        status=PracticeRun.Status.PASSED,
        passed_tests=2,
        total_tests=2,
    )
    reflection = SolutionReflection.objects.create(
        practice_run=run,
        rewritten_approach="Use a set to track values.",
        complexity="O(n) time and O(n) space.",
        mistake_cause="I skipped the empty-input trace.",
        next_correction="Trace one edge case before coding.",
    )

    _, event = set_learning_status(
        problem,
        status=LearningStatus.SOLVED_INDEPENDENTLY,
        reason="I reproduced the solution from memory and explained the invariant.",
        practice_run=run,
        reflection=reflection,
    )

    assert event.practice_run_id == run.pk
    assert event.reflection_id == reflection.pk
    assert event.problem_snapshot.title == problem.title
    assert event.problem_snapshot.version == 1


@pytest.mark.django_db
def test_status_route_saves_choice_reason_and_history(client, problem):
    response = client.post(
        status_url(problem),
        data=status_payload(
            LearningStatus.SOLVED_WITH_HELP,
            "I needed a hint for the stopping condition, then solved the rest.",
        ),
    )

    assert response.status_code == 302
    assert response["Location"].endswith("/practice/contains-duplicate/?status_saved=1")

    editor = client.get(response["Location"])
    body = editor.content.decode()
    current = ProblemLearningStatus.objects.get(problem=problem)

    assert current.status == LearningStatus.SOLVED_WITH_HELP
    assert current.events.count() == 1
    assert 'data-testid="learning-status-saved"' in body
    assert "Learning Status: Solved with help" in body
    assert "I needed a hint for the stopping condition" in body
    assert 'data-testid="learning-status-event"' in body


@pytest.mark.django_db
def test_status_route_renders_validation_error_without_writing(client, problem):
    response = client.post(status_url(problem), data={"status": "attempted", "reason": " "})

    assert response.status_code == 200
    assert "Add one short reason so the next revisit has useful context." in response.content.decode()
    assert not ProblemLearningStatus.objects.get(problem=problem).events.exists()


@pytest.mark.django_db
def test_editor_separates_passing_result_from_unseen_learning_status(client, problem):
    run_visible_tests(
        problem,
        code="def contains_duplicate(nums):\n    return len(nums) != len(set(nums))\n",
    )

    response = client.get(reverse("practice:editor", kwargs={"slug": problem.slug}))
    body = response.content.decode()

    assert response.status_code == 200
    assert "Passed" in body
    assert "Learning Status: Unseen" in body
    assert "Passing runs never mark independent mastery automatically." in body
    assert 'value="solved_independently"' in body
    assert 'data-testid="learning-status-form"' in body
    assert not LearningStatusEvent.objects.exists()


@pytest.mark.django_db
def test_evidence_must_belong_to_the_same_problem(problem, other_problem):
    other_run = PracticeRun.objects.create(
        problem=other_problem,
        code="def other():\n    return True\n",
        status=PracticeRun.Status.PASSED,
    )

    with pytest.raises(ValidationError):
        set_learning_status(
            problem,
            status=LearningStatus.ATTEMPTED,
            reason="This evidence belongs elsewhere.",
            practice_run=other_run,
        )

    assert not ProblemLearningStatus.objects.filter(problem=problem).exists()
