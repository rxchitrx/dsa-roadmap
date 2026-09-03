import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from problems.models import Problem

from practice.forms import SolutionReflectionForm
from practice.models import PracticeRun, SolutionReflection


@pytest.fixture
def problem(db):
    return Problem.objects.create(
        title="Contains Duplicate",
        slug="contains-duplicate",
        statement="Return whether any value appears more than once.",
        source_name="LeetCode",
        source_problem_id="217",
    )


@pytest.fixture
def practice_run(problem):
    return PracticeRun.objects.create(
        problem=problem,
        code="def contains_duplicate(nums):\n    return len(nums) != len(set(nums))\n",
        status=PracticeRun.Status.PASSED,
        passed_tests=2,
        total_tests=2,
        duration_ms=18,
        details=[{"label": "duplicates are detected", "passed": True}],
    )


def reflection_url(problem, practice_run):
    return reverse(
        "practice:reflection",
        kwargs={"slug": problem.slug, "run_id": practice_run.pk},
    )


def reflection_payload(**overrides):
    payload = {
        "rewritten_approach": "Track values in a set and stop when a value repeats.",
        "complexity": "O(n) time and O(n) space because each value is stored once.",
        "mistake_cause": "I forgot to check the repeated value before returning.",
        "next_correction": "Trace the first duplicate by hand before I code.",
        "notes": "Use an empty input as a quick edge case.",
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_reflection_is_persisted_against_one_exact_practice_run(practice_run):
    reflection = SolutionReflection.objects.create(
        practice_run=practice_run,
        **reflection_payload(),
    )

    assert reflection.practice_run_id == practice_run.pk
    assert practice_run.reflection == reflection
    assert str(reflection) == (
        f"Reflection for Contains Duplicate run #{practice_run.pk}"
    )

    with pytest.raises(ValidationError):
        SolutionReflection(
            practice_run=practice_run,
            **reflection_payload(rewritten_approach="   "),
        ).full_clean()


@pytest.mark.django_db
def test_reflection_form_requires_the_four_learning_fields():
    form = SolutionReflectionForm(
        data=reflection_payload(
            rewritten_approach=" ",
            complexity="",
            mistake_cause="\n\t",
            next_correction=" ",
        )
    )

    assert not form.is_valid()
    assert set(form.errors) == {
        "rewritten_approach",
        "complexity",
        "mistake_cause",
        "next_correction",
    }


@pytest.mark.django_db
def test_reflection_page_shows_the_selected_run_and_history_snapshot(
    client,
    problem,
    practice_run,
):
    response = client.get(reflection_url(problem, practice_run))

    assert response.status_code == 200
    body = response.content.decode()
    assert 'data-testid="reflection-page"' in body
    assert 'data-testid="reflection-form"' in body
    assert "Run snapshot" in body
    assert "Passed" in body
    assert "2 of 2 visible tests passed." in body
    assert "def contains_duplicate(nums):" in body
    assert "Rewritten approach" in body
    assert not SolutionReflection.objects.exists()


@pytest.mark.django_db
def test_reflection_route_saves_and_reloads_values(client, problem, practice_run):
    url = reflection_url(problem, practice_run)
    response = client.post(url, data=reflection_payload())

    assert response.status_code == 302
    assert response["Location"] == f"{url}?saved=1"

    reflection = SolutionReflection.objects.get(practice_run=practice_run)
    assert reflection.rewritten_approach == reflection_payload()["rewritten_approach"]
    assert reflection.notes == reflection_payload()["notes"]

    saved_page = client.get(response["Location"])
    body = saved_page.content.decode()
    assert saved_page.status_code == 200
    assert 'data-testid="reflection-saved"' in body
    assert "Future-you has something concrete to revisit." in body
    assert reflection_payload()["next_correction"] in body


@pytest.mark.django_db
def test_reflection_route_edits_the_existing_reflection(client, problem, practice_run):
    url = reflection_url(problem, practice_run)
    client.post(url, data=reflection_payload())
    reflection = SolutionReflection.objects.get(practice_run=practice_run)

    updated = reflection_payload(
        rewritten_approach="Use a set as the invariant: every stored value has appeared earlier.",
        notes="Revisit this before the next assessment.",
    )
    response = client.post(url, data=updated)

    assert response.status_code == 302
    reflection.refresh_from_db()
    assert reflection.pk == SolutionReflection.objects.get(
        practice_run=practice_run
    ).pk
    assert reflection.rewritten_approach == updated["rewritten_approach"]
    assert reflection.notes == updated["notes"]
    assert SolutionReflection.objects.filter(practice_run=practice_run).count() == 1


@pytest.mark.django_db
def test_invalid_reflection_submission_renders_errors_without_persisting(
    client,
    problem,
    practice_run,
):
    response = client.post(
        reflection_url(problem, practice_run),
        data={},
    )

    assert response.status_code == 200
    body = response.content.decode()
    assert "Write the approach you would use next time." in body
    assert "Record the time and space complexity." in body
    assert "Name the cause of the mistake or hesitation." in body
    assert "Write one concrete correction for your next attempt." in body
    assert not SolutionReflection.objects.exists()


@pytest.mark.django_db
def test_editor_prompts_for_reflection_on_the_latest_run(client, problem, practice_run):
    response = client.get(reverse("practice:editor", kwargs={"slug": problem.slug}))

    assert response.status_code == 200
    body = response.content.decode()
    assert 'data-testid="reflection-prompt"' in body
    assert 'data-testid="reflection-link"' in body
    assert f'href="{reflection_url(problem, practice_run)}"' in body


@pytest.mark.django_db
def test_reflection_cannot_use_a_run_from_another_problem(client, problem, practice_run):
    other_problem = Problem.objects.create(
        title="Other problem",
        slug="other-problem",
        statement="Return a value.",
    )

    response = client.get(reflection_url(other_problem, practice_run))

    assert response.status_code == 404
