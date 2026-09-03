from collections.abc import Iterator, Mapping

import pytest
from django.test import override_settings
from django.urls import reverse

from problems.catalog_sync import sync_catalog
from problems.models import Problem, ProblemSnapshot
from problems.services import ensure_problem_snapshot


class FakeSource:
    total = 1

    def __init__(self, item):
        self.item = item

    def iter_batches(self) -> Iterator[tuple[Mapping, ...]]:
        yield (self.item,)


def public_problem(
    *,
    title="Two Sum",
    title_slug="two-sum",
    statement="Find a pair.",
    difficulty="Easy",
    tags=None,
    is_paid_only=False,
):
    return {
        "title": title,
        "titleSlug": title_slug,
        "frontendQuestionId": "1",
        "difficulty": difficulty,
        "content": statement,
        "topicTags": tags or [{"name": "Two Pointers", "slug": "two-pointers"}],
        "isPaidOnly": is_paid_only,
    }


@pytest.mark.django_db
def test_unchanged_catalog_sync_keeps_one_active_snapshot():
    source_item = public_problem()

    sync_catalog(source=FakeSource(source_item))
    sync_catalog(source=FakeSource(source_item))

    problem = Problem.objects.get(source_problem_id="1")
    snapshots = list(problem.snapshots.order_by("version"))

    assert len(snapshots) == 1
    assert snapshots[0].version == 1
    assert snapshots[0].is_active is True
    assert problem.active_snapshot == snapshots[0]
    assert snapshots[0].statement == "Find a pair."


@pytest.mark.django_db
def test_changed_catalog_sync_closes_old_snapshot_and_opens_next_version():
    sync_catalog(source=FakeSource(public_problem()))
    sync_catalog(
        source=FakeSource(
            public_problem(
                title="Two Sum · Revised",
                title_slug="two-sum-revised",
                statement="Find a pair efficiently.",
                difficulty="Medium",
                tags=[{"name": "Hash Table", "slug": "hash-table"}],
                is_paid_only=True,
            )
        )
    )

    problem = Problem.objects.get(source_problem_id="1")
    snapshots = list(problem.snapshots.order_by("version"))
    active = problem.active_snapshot

    assert [snapshot.version for snapshot in snapshots] == [1, 2]
    assert [snapshot.is_active for snapshot in snapshots] == [False, True]
    assert ProblemSnapshot.objects.filter(problem=problem, is_active=True).count() == 1
    assert snapshots[0].title == "Two Sum"
    assert snapshots[0].statement == "Find a pair."
    assert snapshots[0].difficulty == Problem.Difficulty.EASY
    assert snapshots[0].source_url.endswith("/two-sum/")
    assert snapshots[1] == active
    assert active.version == 2
    assert active.title == "Two Sum · Revised"
    assert active.statement == "Find a pair efficiently."
    assert active.difficulty == Problem.Difficulty.MEDIUM
    assert active.source_url.endswith("/two-sum-revised/")
    assert active.is_paid_only is True
    assert active.tags == ["Hash Table"]


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="problems.tests.urls")
def test_problem_detail_identifies_the_active_source_snapshot(client):
    problem = Problem.objects.create(
        title="Versioned problem",
        slug="versioned-problem",
        statement="The current source statement.",
        source_name="LeetCode",
        source_problem_id="99",
    )
    ensure_problem_snapshot(problem)

    response = client.get(
        reverse("problems:detail", kwargs={"slug": problem.slug})
    )

    assert response.status_code == 200
    assert 'data-testid="active-problem-snapshot"' in response.content.decode()
    assert "Active source snapshot v1" in response.content.decode()
