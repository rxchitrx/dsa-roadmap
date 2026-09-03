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


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="problems.tests.urls")
def test_problem_detail_renders_statement_examples_and_source_metadata(client, catalog):
    problem = Problem.objects.create(
        concept=catalog["pointers"],
        title="Detail-ready palindrome",
        slug="detail-ready-palindrome",
        statement="Return whether the input reads the same from both ends.",
        difficulty=Problem.Difficulty.EASY,
        source_name="LeetCode",
        source_problem_id="125",
        source_url="https://leetcode.com/problems/valid-palindrome/",
        examples=[
            {
                "input": "s = 'racecar'",
                "output": "true",
                "walkthrough": "Compare matching characters from both ends.",
            }
        ],
    )

    response = client.get(reverse("problems:detail", kwargs={"slug": problem.slug}))

    assert response.status_code == 200
    assert response.context["problem"] == problem
    html = response.content.decode()
    assert "Return whether the input reads the same from both ends." in html
    assert "Example 1" in html
    assert "s = &#x27;racecar&#x27;" in html
    assert "Compare matching characters from both ends." in html
    assert "LeetCode" in html
    assert "ID: 125" in html
    assert "O(n)" in html
    assert 'target="_blank"' in html
    assert 'rel="noopener noreferrer nofollow"' in html
    assert 'href="https://leetcode.com/problems/valid-palindrome/"' in html


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="problems.tests.urls")
def test_problem_detail_shows_missing_optional_fields_without_broken_links(client, catalog):
    problem = Problem.objects.get(slug="unclassified-practice-prompt")

    response = client.get(reverse("problems:detail", kwargs={"slug": problem.slug}))

    assert response.status_code == 200
    html = response.content.decode()
    assert "This record is waiting for catalog metadata." in html
    assert "No examples have been added for this problem yet." in html
    assert "Constraints are not recorded yet." in html
    assert "Expected complexity is not recorded yet." in html
    assert "Source name and identifier are not recorded yet." in html
    assert "No external source link has been added for this problem." in html
    assert 'target="_blank"' not in html


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="problems.tests.urls")
def test_problem_detail_rejects_unsafe_source_urls(client, catalog):
    problem = Problem.objects.create(
        title="Unsafe source sample",
        slug="unsafe-source-sample",
        statement="A source URL should be treated as data, not executable markup.",
        source_name="Imported source",
        source_url="javascript:alert(1)",
    )

    response = client.get(reverse("problems:detail", kwargs={"slug": problem.slug}))

    assert response.status_code == 200
    html = response.content.decode()
    assert "javascript:alert(1)" not in html
    assert "No external source link has been added for this problem." in html


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="problems.tests.urls")
def test_problem_library_links_each_problem_to_its_detail_page(client, catalog):
    response = client.get(reverse("problems:index"))

    assert response.status_code == 200
    html = response.content.decode()
    assert 'href="/problems/valid-palindrome/"' in html


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="problems.tests.urls")
def test_problem_detail_hides_inactive_problems(client, catalog):
    response = client.get(
        reverse("problems:detail", kwargs={"slug": "inactive-old-record"})
    )

    assert response.status_code == 404
