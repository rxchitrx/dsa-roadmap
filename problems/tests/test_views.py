import pytest
from django.test import override_settings
from django.urls import reverse

from curriculum.models import Concept, Topic

from problems.models import Problem


@pytest.fixture
def catalog(db):
    arrays = Topic.objects.create(
        name="Arrays & Strings",
        slug="arrays-strings",
        description="Array foundations",
        display_order=1,
    )
    search = Topic.objects.create(
        name="Search",
        slug="search",
        description="Search foundations",
        display_order=2,
    )
    fundamentals = Concept.objects.create(
        topic=arrays,
        name="Array Fundamentals",
        slug="array-fundamentals",
        order=1,
        summary="Access and scan.",
        intuition="An intuition.",
        explanation="An explanation.",
        complexity_notes="O(n)",
        implementation_guidance="An invariant.",
        common_traps="Off by one.",
        guided_practice="Trace it.",
        checkpoint="Explain it.",
    )
    pointers = Concept.objects.create(
        topic=arrays,
        name="Two Pointers",
        slug="two-pointers",
        order=2,
        summary="Move two boundaries.",
        intuition="An intuition.",
        explanation="An explanation.",
        complexity_notes="O(n)",
        implementation_guidance="An invariant.",
        common_traps="Off by one.",
        guided_practice="Trace it.",
        checkpoint="Explain it.",
    )
    binary_search = Concept.objects.create(
        topic=search,
        name="Binary Search",
        slug="binary-search",
        order=1,
        summary="Halve a search space.",
        intuition="An intuition.",
        explanation="An explanation.",
        complexity_notes="O(log n)",
        implementation_guidance="An invariant.",
        common_traps="Off by one.",
        guided_practice="Trace it.",
        checkpoint="Explain it.",
    )
    Problem.objects.bulk_create(
        [
            Problem(
                concept=pointers,
                title="Valid Palindrome",
                slug="valid-palindrome",
                statement="Check whether a string reads the same both ways.",
                difficulty=Problem.Difficulty.EASY,
                source_name="LeetCode",
                source_problem_id="125",
                tags=["string", "two-pointers"],
                display_order=3,
            ),
            Problem(
                concept=fundamentals,
                title="Contains Duplicate",
                slug="contains-duplicate",
                statement="Find repeated values in an array.",
                difficulty=Problem.Difficulty.EASY,
                source_name="LeetCode",
                source_problem_id="217",
                tags=["array", "hash-set"],
                display_order=1,
            ),
            Problem(
                concept=binary_search,
                title="Search Insert Position",
                slug="search-insert-position",
                statement="Find the place where target belongs in a sorted array.",
                difficulty=Problem.Difficulty.MEDIUM,
                source_name="LeetCode",
                source_problem_id="35",
                tags=["binary-search"],
                display_order=2,
            ),
            Problem(
                title="Unclassified practice prompt",
                slug="unclassified-practice-prompt",
                statement="This record is waiting for catalog metadata.",
                tags=[],
                display_order=4,
            ),
            Problem(
                concept=fundamentals,
                title="Inactive old record",
                slug="inactive-old-record",
                statement="It should not appear in the active shelf.",
                difficulty=Problem.Difficulty.HARD,
                source_name="LeetCode",
                is_active=False,
            ),
        ]
    )

    return {
        "arrays": arrays,
        "fundamentals": fundamentals,
        "pointers": pointers,
        "binary_search": binary_search,
    }


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="problems.tests.urls")
def test_problem_library_orders_active_problems_by_title(client, catalog):
    response = client.get(reverse("problems:index"))

    assert response.status_code == 200
    assert [problem.title for problem in response.context["problems"]] == [
        "Contains Duplicate",
        "Search Insert Position",
        "Unclassified practice prompt",
        "Valid Palindrome",
    ]
    assert "Inactive old record" not in response.content.decode()


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="problems.tests.urls")
def test_problem_library_combines_topic_concept_and_difficulty_filters(client, catalog):
    response = client.get(
        reverse("problems:index"),
        {
            "topic": "arrays-strings",
            "concept": "two-pointers",
            "difficulty": "easy",
        },
    )

    assert response.status_code == 200
    assert [problem.title for problem in response.context["problems"]] == ["Valid Palindrome"]
    assert "Contains Duplicate" not in response.content.decode()
    assert "Two Pointers" in response.content.decode()


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="problems.tests.urls")
def test_problem_library_search_can_be_combined_with_a_filter(client, catalog):
    response = client.get(
        reverse("problems:index"),
        {"q": "sorted", "topic": "search"},
    )

    assert response.status_code == 200
    assert [problem.title for problem in response.context["problems"]] == ["Search Insert Position"]


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="problems.tests.urls")
def test_problem_library_shows_metadata_warning_and_no_match_state(client, catalog):
    missing_metadata_response = client.get(reverse("problems:index"))
    empty_response = client.get(
        reverse("problems:index"),
        {"difficulty": "hard", "topic": "search", "q": "not here"},
    )

    missing_html = missing_metadata_response.content.decode()
    empty_html = empty_response.content.decode()
    assert "1 problem need metadata review" in missing_html
    assert "Needs concept classification" in missing_html
    assert "That combination is empty." in empty_html
    assert "Show all problems" in empty_html
