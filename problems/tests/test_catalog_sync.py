from collections.abc import Iterator, Mapping

import pytest
from django.test import override_settings
from django.urls import reverse

from curriculum.models import Concept, Topic

from problems.catalog_sync import (
    CatalogSyncError,
    LeetCodeCatalogClient,
    sync_catalog,
)
from problems.models import CatalogSync, Problem, ProblemClassification


class FakeSource:
    def __init__(self, batches, *, total=None):
        self.batches = batches
        self.total = total

    def iter_batches(self) -> Iterator[tuple[Mapping, ...]]:
        yield from self.batches


class OfflineSource:
    total = None

    def iter_batches(self):
        raise OSError("network unavailable")
        yield ()


def public_problem(*, title="Two Sum", source_id="1", statement="<p>Find a pair.</p>", tags=None):
    return {
        "title": title,
        "titleSlug": title.lower().replace(" ", "-"),
        "frontendQuestionId": source_id,
        "difficulty": "Easy",
        "content": statement,
        "topicTags": tags or [{"name": "Two Pointers", "slug": "two-pointers"}],
        "isPaidOnly": False,
    }


@pytest.fixture
def two_pointers_concept(db):
    topic = Topic.objects.create(
        name="Arrays",
        slug="catalog-sync-arrays",
        description="Catalog sync fixtures",
    )
    return Concept.objects.create(
        topic=topic,
        name="Two Pointers",
        slug="two-pointers",
        order=1,
        summary="Move two boundaries.",
        intuition="Shrink the search space.",
        explanation="Keep a left and right boundary.",
        complexity_notes="O(n)",
        implementation_guidance="State the invariant.",
        common_traps="Move the correct boundary.",
        guided_practice="Trace both pointers.",
        checkpoint="Explain why the search space shrinks.",
    )


@pytest.mark.django_db
def test_public_catalog_import_is_idempotent_and_updates_source_metadata(two_pointers_concept):
    first = sync_catalog(
        source=FakeSource([[public_problem(statement="<p>Find a pair.</p>")]], total=1)
    )

    problem = Problem.objects.get(source_name="LeetCode", source_problem_id="1")
    assert first.status == CatalogSync.Status.SUCCEEDED
    assert first.imported_count == 1
    assert first.updated_count == 0
    assert Problem.objects.count() == 1
    assert problem.statement == "Find a pair."
    assert problem.source_url == "https://leetcode.com/problems/two-sum/"

    second = sync_catalog(
        source=FakeSource(
            [[public_problem(statement="<p>Find a pair efficiently.</p>")]],
            total=1,
        )
    )

    problem.refresh_from_db()
    assert second.status == CatalogSync.Status.SUCCEEDED
    assert second.imported_count == 0
    assert second.updated_count == 1
    assert Problem.objects.count() == 1
    assert problem.statement == "Find a pair efficiently."
    assert problem.classifications.count() == 1


@pytest.mark.django_db
def test_public_topic_match_is_an_uncertain_classification_warning(two_pointers_concept):
    run = sync_catalog(
        source=FakeSource([[public_problem(source_id="15")]], total=1)
    )

    problem = Problem.objects.get(source_problem_id="15")
    classification = ProblemClassification.objects.get(problem=problem)
    assert run.classification_warning_count == 1
    assert classification.status == ProblemClassification.Status.UNCERTAIN
    assert classification.note
    assert problem.has_classification_warning is True
    assert "Concept classification is uncertain" in problem.metadata_warnings


@pytest.mark.django_db
def test_pagination_adapter_requests_batches_until_public_total_is_consumed():
    responses = [
        {
            "data": {
                "problemsetQuestionList": {
                    "total": 5,
                    "questions": [
                        public_problem(title="First", source_id="1"),
                        public_problem(title="Second", source_id="2"),
                    ],
                }
            }
        },
        {
            "data": {
                "problemsetQuestionList": {
                    "total": 5,
                    "questions": [
                        public_problem(title="Third", source_id="3"),
                        public_problem(title="Fourth", source_id="4"),
                    ],
                }
            }
        },
        {
            "data": {
                "problemsetQuestionList": {
                    "total": 5,
                    "questions": [public_problem(title="Fifth", source_id="5")],
                }
            }
        },
    ]
    requests = []

    def request_json(payload):
        requests.append(payload)
        return responses.pop(0)

    client = LeetCodeCatalogClient(batch_size=2, request_json=request_json)

    batches = list(client.iter_batches())

    assert [[item["frontendQuestionId"] for item in batch] for batch in batches] == [
        ["1", "2"],
        ["3", "4"],
        ["5"],
    ]
    assert [request["variables"]["skip"] for request in requests] == [0, 2, 4]
    assert [request["variables"]["limit"] for request in requests] == [2, 2, 2]
    assert client.total == 5


@pytest.mark.django_db
def test_offline_failure_keeps_last_successful_catalog_available(two_pointers_concept):
    sync_catalog(
        source=FakeSource([[public_problem(source_id="42")]], total=1)
    )
    problem = Problem.objects.get(source_problem_id="42")

    with pytest.raises(CatalogSyncError, match="network unavailable"):
        sync_catalog(source=OfflineSource())

    problem.refresh_from_db()
    latest = CatalogSync.objects.first()
    last_success = CatalogSync.objects.filter(status=CatalogSync.Status.SUCCEEDED).first()
    assert latest.status == CatalogSync.Status.FAILED
    assert "network unavailable" in latest.error_message
    assert last_success is not None
    assert problem.is_active is True
    assert Problem.objects.filter(source_problem_id="42", is_active=True).exists()


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="problems.tests.urls")
def test_problem_library_exposes_failed_sync_and_safe_fallback(client, two_pointers_concept):
    sync_catalog(
        source=FakeSource([[public_problem(source_id="42")]], total=1)
    )
    with pytest.raises(CatalogSyncError):
        sync_catalog(source=OfflineSource())

    response = client.get(reverse("problems:index"))

    assert response.status_code == 200
    html = response.content.decode()
    assert 'data-testid="catalog-sync-status"' in html
    assert "The last sync failed" in html
    assert "Your last successful catalog is still available." in html
    assert "Two Sum" in html


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="problems.tests.urls")
def test_catalog_status_endpoint_exposes_persisted_progress(client):
    CatalogSync.objects.create(
        status=CatalogSync.Status.RUNNING,
        total_items=100,
        processed_items=40,
        current_batch=2,
        imported_count=40,
    )

    response = client.get(reverse("problems:sync_status"))

    assert response.status_code == 200
    assert response.json() == {
        "status": "running",
        "label": "Syncing",
        "progress": "40 of 100 problems",
        "processed_items": 40,
        "total_items": 100,
        "imported_count": 40,
        "updated_count": 0,
        "classification_warning_count": 0,
        "error_message": "",
        "last_success_at": None,
    }
