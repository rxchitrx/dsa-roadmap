import json

import pytest
from django.urls import reverse

from problems.models import Problem

from practice.models import CustomTestCase, PracticeRun, ProblemDraft
from practice.services import run_visible_tests, save_custom_tests, starter_signature_for


@pytest.fixture
def problem(db):
    return Problem.objects.create(
        title="Contains Duplicate",
        slug="contains-duplicate",
        statement="Return whether any value appears more than once.",
        difficulty=Problem.Difficulty.EASY,
        source_name="LeetCode",
        source_problem_id="217",
        examples=[{"input": "nums = [1, 2, 1]", "output": "true"}],
    )


def post_draft(client, problem, *, code, base_revision):
    return client.post(
        reverse("practice:save_draft", kwargs={"slug": problem.slug}),
        data=json.dumps({"code": code, "base_revision": base_revision}),
        content_type="application/json",
    )


def post_custom_tests(client, problem, cases):
    return client.post(
        reverse("practice:save_custom_tests", kwargs={"slug": problem.slug}),
        data=json.dumps({"cases": cases}),
        content_type="application/json",
    )


@pytest.mark.django_db
def test_editor_creates_initial_problem_specific_draft(client, problem):
    response = client.get(
        reverse("practice:editor", kwargs={"slug": problem.slug})
    )

    assert response.status_code == 200
    draft = ProblemDraft.objects.get(problem=problem)
    assert draft.revision == 1
    assert draft.starter_signature == "def contains_duplicate(nums):"
    assert draft.code.startswith("def contains_duplicate(nums):")
    assert "def contains_duplicate(nums):" in response.content.decode()
    assert response.context["draft"] == draft


@pytest.mark.django_db
def test_editor_includes_a_reflection_target_that_can_be_updated_after_first_run(
    client, problem
):
    response = client.get(reverse("practice:editor", kwargs={"slug": problem.slug}))

    assert response.status_code == 200
    body = response.content.decode()
    assert 'data-reflection-prompt' in body
    assert 'data-reflection-link' in body
    assert 'data-reflection-url-template="/practice/contains-duplicate/runs/0/reflection/"' in body
    assert 'href="#"' in body
    assert 'hidden' in body


@pytest.mark.django_db
def test_autosave_persists_code_and_advances_revision(client, problem):
    client.get(reverse("practice:editor", kwargs={"slug": problem.slug}))

    code = "def contains_duplicate(nums):\n    return len(nums) != len(set(nums))\n"
    response = post_draft(client, problem, code=code, base_revision=1)

    assert response.status_code == 200
    assert response.json()["saved"] is True
    assert response.json()["revision"] == 2
    draft = ProblemDraft.objects.get(problem=problem)
    assert draft.code == code
    assert draft.revision == 2


@pytest.mark.django_db
def test_reload_restores_latest_saved_draft(client, problem):
    client.get(reverse("practice:editor", kwargs={"slug": problem.slug}))
    code = "def contains_duplicate(nums):\n    seen = set()\n    return False\n"
    post_draft(client, problem, code=code, base_revision=1)

    response = client.get(reverse("practice:editor", kwargs={"slug": problem.slug}))

    assert response.status_code == 200
    assert response.context["draft"].code == code
    assert code in response.content.decode()
    assert "Revision 2" in response.content.decode()


@pytest.mark.django_db
def test_stale_autosave_cannot_overwrite_newer_draft(client, problem):
    client.get(reverse("practice:editor", kwargs={"slug": problem.slug}))
    latest_code = "def contains_duplicate(nums):\n    return True\n"
    stale_code = "def contains_duplicate(nums):\n    return False\n"

    first_response = post_draft(
        client,
        problem,
        code=latest_code,
        base_revision=1,
    )
    stale_response = post_draft(
        client,
        problem,
        code=stale_code,
        base_revision=1,
    )

    assert first_response.status_code == 200
    assert stale_response.status_code == 409
    assert stale_response.json() == {
        "saved": False,
        "stale": True,
        "revision": 2,
        "code": latest_code,
        "message": "This autosave was based on an older draft.",
    }
    draft = ProblemDraft.objects.get(problem=problem)
    assert draft.code == latest_code
    assert draft.revision == 2


@pytest.mark.django_db
def test_unknown_problem_gets_stable_problem_specific_signature(client, db):
    problem = Problem.objects.create(
        title="Pair values",
        slug="pair-values",
        statement="Find a pair.",
    )

    response = client.get(reverse("practice:editor", kwargs={"slug": problem.slug}))

    assert response.status_code == 200
    assert starter_signature_for(problem) == "def pair_values(data):"
    assert response.context["draft"].starter_signature == "def pair_values(data):"


@pytest.mark.django_db
def test_editor_does_not_recreate_or_reset_an_existing_draft(client, problem):
    first = client.get(reverse("practice:editor", kwargs={"slug": problem.slug}))
    draft = first.context["draft"]
    draft.code = "def contains_duplicate(nums):\n    return 'keep me'\n"
    draft.revision = 4
    draft.save()

    second = client.get(reverse("practice:editor", kwargs={"slug": problem.slug}))

    assert second.context["draft"].pk == draft.pk
    assert second.context["draft"].code == "def contains_duplicate(nums):\n    return 'keep me'\n"
    assert second.context["draft"].revision == 4


@pytest.mark.django_db
def test_run_visible_tests_persists_a_passing_result_and_editor_shows_it(client, problem):
    code = "def contains_duplicate(nums):\n    return len(nums) != len(set(nums))\n"

    response = client.post(
        reverse("practice:run_tests", kwargs={"slug": problem.slug}),
        data=json.dumps({"code": code}),
        content_type="application/json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run"] is True
    assert payload["status"] == PracticeRun.Status.PASSED
    assert payload["passed_tests"] == 2
    assert payload["total_tests"] == 2
    assert PracticeRun.objects.get(problem=problem).code == code

    editor = client.get(reverse("practice:editor", kwargs={"slug": problem.slug}))
    assert "Passed" in editor.content.decode()
    assert "2 of 2 visible tests passed." in editor.content.decode()


@pytest.mark.django_db
def test_run_visible_tests_reports_an_assertion_failure(problem):
    code = "def contains_duplicate(nums):\n    return len(nums) == len(set(nums))\n"

    practice_run = run_visible_tests(problem, code=code)

    assert practice_run.status == PracticeRun.Status.ASSERTION_FAILURE
    assert practice_run.passed_tests == 0
    assert practice_run.total_tests == 2
    assert practice_run.details[0]["passed"] is False
    assert PracticeRun.objects.filter(pk=practice_run.pk).exists()


@pytest.mark.django_db
def test_run_visible_tests_reports_a_runtime_error(problem):
    code = "def contains_duplicate(nums):\n    raise ValueError('bad input')\n"

    practice_run = run_visible_tests(problem, code=code)

    assert practice_run.status == PracticeRun.Status.RUNTIME_ERROR
    assert practice_run.passed_tests == 0
    assert "ValueError: bad input" in practice_run.details[0]["message"]


@pytest.mark.django_db
def test_run_visible_tests_stops_a_non_terminating_submission(problem):
    code = "def contains_duplicate(nums):\n    while True:\n        pass\n"

    practice_run = run_visible_tests(problem, code=code)

    assert practice_run.status == PracticeRun.Status.TIMEOUT
    assert practice_run.total_tests == 2
    assert practice_run.duration_ms >= 1_000


@pytest.mark.django_db
def test_run_visible_tests_rejects_filesystem_and_network_capabilities(problem):
    code = "import os\n\ndef contains_duplicate(nums):\n    return os.listdir('/')\n"

    practice_run = run_visible_tests(problem, code=code)

    assert practice_run.status == PracticeRun.Status.SAFETY_VIOLATION
    assert "Imports are disabled" in practice_run.message
    assert not practice_run.details


@pytest.mark.django_db
def test_custom_tests_can_be_added_edited_reordered_and_removed(problem):
    first = save_custom_tests(
        problem,
        [
            {
                "label": "Empty input",
                "input_data": [[]],
                "expected_output": False,
            },
            {
                "label": "Repeated at the end",
                "input_data": [[1, 2, 3, 3]],
                "expected_output": True,
            },
        ],
    )

    assert [case.label for case in first] == ["Empty input", "Repeated at the end"]
    assert [case.position for case in first] == [0, 1]

    second = save_custom_tests(
        problem,
        [
            {
                "id": first[1].pk,
                "label": "Edited duplicate",
                "input_data": [[4, 4]],
                "expected_output": True,
            }
        ],
    )

    assert len(second) == 1
    assert second[0].pk == first[1].pk
    assert second[0].label == "Edited duplicate"
    assert second[0].position == 0
    assert not CustomTestCase.objects.filter(pk=first[0].pk).exists()


@pytest.mark.django_db
def test_custom_test_route_persists_cases_and_editor_renders_them(client, problem):
    response = post_custom_tests(
        client,
        problem,
        [
            {
                "label": "Single value",
                "input_data": [[8]],
                "expected_output": False,
            }
        ],
    )

    assert response.status_code == 200
    assert response.json()["saved"] is True
    assert response.json()["cases"][0]["label"] == "Single value"

    editor = client.get(reverse("practice:editor", kwargs={"slug": problem.slug}))

    assert editor.status_code == 200
    body = editor.content.decode()
    assert "Custom visible tests" in body
    assert "Single value" in body
    assert "[[8]]" in body
    assert "data-remove-custom-test" in body


@pytest.mark.django_db
def test_malformed_custom_cases_are_rejected_before_execution(client, problem):
    response = client.post(
        reverse("practice:run_tests", kwargs={"slug": problem.slug}),
        data=json.dumps(
            {
                "code": "def contains_duplicate(nums):\n    return len(nums) != len(set(nums))\n",
                "custom_tests": [
                    {
                        "label": "Not an argument list",
                        "input_data": {"nums": [1, 1]},
                        "expected_output": True,
                    }
                ],
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["run"] is False
    assert payload["validation_errors"][0]["field"] == "input"
    assert PracticeRun.objects.count() == 0
    assert CustomTestCase.objects.count() == 0


@pytest.mark.django_db
def test_runner_reports_mixed_default_and_custom_results(problem):
    custom_case = CustomTestCase.objects.create(
        problem=problem,
        label="No duplicate should be false",
        input_data=[[1, 2, 3]],
        expected_output=True,
        position=0,
    )
    code = "def contains_duplicate(nums):\n    return len(nums) != len(set(nums))\n"

    practice_run = run_visible_tests(problem, code=code)

    assert practice_run.status == PracticeRun.Status.ASSERTION_FAILURE
    assert practice_run.passed_tests == 2
    assert practice_run.total_tests == 3
    assert [detail["kind"] for detail in practice_run.details] == [
        "default",
        "default",
        "custom",
    ]
    assert practice_run.details[-1]["case_id"] == custom_case.pk
    assert practice_run.details[0]["passed"] is True
    assert practice_run.details[1]["passed"] is True
    assert practice_run.details[2]["passed"] is False


@pytest.mark.django_db
def test_run_route_saves_custom_cases_and_returns_mixed_results(client, problem):
    response = client.post(
        reverse("practice:run_tests", kwargs={"slug": problem.slug}),
        data=json.dumps(
            {
                "code": "def contains_duplicate(nums):\n    return len(nums) != len(set(nums))\n",
                "custom_tests": [
                    {
                        "label": "Duplicate pair",
                        "input_data": [[5, 5]],
                        "expected_output": True,
                    }
                ],
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run"] is True
    assert payload["passed_tests"] == 3
    assert payload["total_tests"] == 3
    assert payload["custom_tests"][0]["label"] == "Duplicate pair"
    assert payload["details"][-1]["kind"] == "custom"
    assert CustomTestCase.objects.filter(label="Duplicate pair").exists()


@pytest.mark.django_db
def test_custom_test_delete_route_removes_only_current_problem_case(client, problem, db):
    other_problem = Problem.objects.create(
        title="Other problem",
        slug="other-problem",
        statement="Return a value.",
    )
    case = CustomTestCase.objects.create(
        problem=problem,
        label="Delete me",
        input_data=[[]],
        expected_output=None,
    )
    other_case = CustomTestCase.objects.create(
        problem=other_problem,
        label="Keep me",
        input_data=[[]],
        expected_output=None,
    )

    response = client.post(
        reverse(
            "practice:delete_custom_test",
            kwargs={"slug": problem.slug, "case_id": case.pk},
        )
    )

    assert response.status_code == 200
    assert response.json() == {"deleted": True, "id": case.pk}
    assert not CustomTestCase.objects.filter(pk=case.pk).exists()
    assert CustomTestCase.objects.filter(pk=other_case.pk).exists()
