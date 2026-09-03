from collections.abc import Iterator, Mapping
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from practice.models import PracticeRun, ProblemDraft
from problems.catalog_sync import sync_catalog
from problems.models import Problem

from history.models import RunHistoryEntry


class FakeSource:
    total = 1

    def __init__(self, item):
        self.item = item

    def iter_batches(self) -> Iterator[tuple[Mapping, ...]]:
        yield (self.item,)


def catalog_problem(*, title, statement, title_slug):
    return {
        "title": title,
        "titleSlug": title_slug,
        "frontendQuestionId": "217",
        "difficulty": "Easy",
        "content": statement,
        "topicTags": [],
        "isPaidOnly": False,
    }


@pytest.fixture
def problem(db):
    return Problem.objects.create(
        title="Contains Duplicate",
        slug="contains-duplicate",
        statement="Return whether any value appears more than once.",
        source_name="LeetCode",
        source_problem_id="217",
    )


def create_run(problem, *, code, status=PracticeRun.Status.PASSED, created_at=None):
    run = PracticeRun.objects.create(
        problem=problem,
        code=code,
        status=status,
        passed_tests=2 if status == PracticeRun.Status.PASSED else 0,
        total_tests=2,
        duration_ms=42,
    )
    if created_at is not None:
        PracticeRun.objects.filter(pk=run.pk).update(created_at=created_at)
        RunHistoryEntry.objects.filter(practice_run=run).update(captured_at=created_at)
    return run


@pytest.mark.django_db
def test_new_practice_run_creates_a_stable_history_snapshot(problem):
    code = "def contains_duplicate(nums):\n    return True\n"
    run = create_run(problem, code=code)

    entry = RunHistoryEntry.objects.get(practice_run=run)

    assert entry.code_snapshot == code
    assert entry.status == PracticeRun.Status.PASSED
    assert entry.result_summary == "2 of 2 visible tests passed."
    assert entry.captured_at == run.created_at

    run.code = "def contains_duplicate(nums):\n    return False\n"
    run.save(update_fields=["code"])
    entry.refresh_from_db()
    assert entry.code_snapshot == code


@pytest.mark.django_db
def test_history_entries_are_ordered_newest_first(problem):
    older = create_run(
        problem,
        code="def contains_duplicate(nums):\n    return False\n",
        created_at=timezone.now() - timedelta(days=1),
    )
    newer = create_run(
        problem,
        code="def contains_duplicate(nums):\n    return True\n",
        created_at=timezone.now(),
    )

    entries = list(RunHistoryEntry.objects.all())

    assert [entry.practice_run_id for entry in entries] == [newer.pk, older.pk]


@pytest.mark.django_db
def test_history_route_renders_result_and_code_snapshot(client, problem):
    code = "def contains_duplicate(nums):\n    return len(nums) != len(set(nums))\n"
    create_run(problem, code=code)

    response = client.get(reverse("history:index"))
    body = response.content.decode()

    assert response.status_code == 200
    assert response.context["entry_count"] == 1
    assert 'data-testid="history-entry"' in body
    assert "Contains Duplicate" in body
    assert "2 of 2 visible tests passed." in body
    assert "Submitted code snapshot" in body
    assert "len(nums) != len(set(nums))" in body
    assert reverse("practice:editor", kwargs={"slug": problem.slug}) in body


@pytest.mark.django_db
def test_history_read_uses_the_problem_snapshot_from_the_original_run(client, problem):
    run = create_run(
        problem,
        code="def contains_duplicate(nums):\n    return True\n",
    )
    original_snapshot = run.history_entry.problem_snapshot

    sync_catalog(
        source=FakeSource(
            catalog_problem(
                title="Contains Duplicate · Revised",
                title_slug="contains-duplicate-revised",
                statement="The source statement has changed since this run.",
            )
        )
    )

    run.history_entry.refresh_from_db()
    response = client.get(reverse("history:index"))
    body = response.content.decode()

    assert response.status_code == 200
    assert run.history_entry.problem_snapshot_id == original_snapshot.pk
    assert run.history_entry.problem_snapshot.title == "Contains Duplicate"
    assert run.history_entry.problem_snapshot.statement == (
        "Return whether any value appears more than once."
    )
    assert "Return whether any value appears more than once." in body
    assert "The source statement has changed since this run." not in body
    assert "Source snapshot v1" in body
    assert "Contains Duplicate" in body


@pytest.mark.django_db
def test_history_route_backfills_a_preexisting_run(client, problem):
    run = create_run(problem, code="def contains_duplicate(nums):\n    return True\n")
    RunHistoryEntry.objects.filter(practice_run=run).delete()

    response = client.get(reverse("history:index"))

    assert response.status_code == 200
    assert RunHistoryEntry.objects.filter(practice_run=run).exists()
    assert response.context["entry_count"] == 1


@pytest.mark.django_db
def test_history_filter_limits_entries_to_one_problem(client, problem):
    other = Problem.objects.create(
        title="Reverse String",
        slug="reverse-string",
        statement="Reverse the characters in place.",
    )
    create_run(problem, code="def contains_duplicate(nums):\n    return True\n")
    create_run(other, code="def reverse_string(chars):\n    return chars\n")

    response = client.get(
        reverse("history:index"),
        {"problem": problem.slug},
    )
    body = response.content.decode()

    assert response.context["entry_count"] == 1
    assert "Contains Duplicate" in body
    assert body.count('data-testid="history-entry"') == 1


@pytest.mark.django_db
def test_autosave_draft_does_not_create_history_entry(client, problem):
    ProblemDraft.objects.create(
        problem=problem,
        starter_signature="def contains_duplicate(nums):",
        code="def contains_duplicate(nums):\n    return None\n",
    )

    response = client.get(reverse("history:index"))

    assert response.status_code == 200
    assert response.context["entry_count"] == 0
    assert not RunHistoryEntry.objects.exists()
