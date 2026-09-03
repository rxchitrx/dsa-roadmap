import json

import pytest
from django.urls import reverse

from problems.models import Problem

from practice.models import ProblemDraft
from practice.services import starter_signature_for


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
