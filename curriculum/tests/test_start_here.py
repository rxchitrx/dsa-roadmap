import pytest
from django.urls import reverse

from curriculum.start_here import (
    START_HERE_DAYS,
    START_HERE_READINESS_CHECKS,
    START_HERE_SOURCES,
)


def test_start_here_manifest_is_a_complete_ordered_fourteen_day_runway():
    assert [day["number"] for day in START_HERE_DAYS] == list(range(1, 15))
    assert len(START_HERE_DAYS) == 14
    assert len(START_HERE_READINESS_CHECKS) >= 6

    for day in START_HERE_DAYS:
        assert day["title"]
        assert day["objective"]
        assert day["minutes"] > 0
        assert day["study"]
        assert day["exercises"]
        assert day["readiness"]
        assert day["source_keys"]
        assert all(key in START_HERE_SOURCES for key in day["source_keys"])


@pytest.mark.django_db
def test_start_here_route_renders_days_sources_and_readiness(client):
    response = client.get(reverse("curriculum:start_here"))

    assert response.status_code == 200
    assert response.context["days"]
    assert len(response.context["days"]) == 14
    html = response.content.decode()
    assert 'data-testid="start-here-page"' in html
    assert html.count('data-testid="start-here-day"') == 14
    assert "Baseline and a tiny Python loop" in html
    assert "READINESS EVIDENCE" in html
    assert "Ready enough to begin." in html
    assert "MIT 6.006 Introduction to Algorithms syllabus" in html
    assert reverse("curriculum:index") in html


@pytest.mark.django_db
def test_today_and_curriculum_link_to_start_here(client):
    today = client.get(reverse("planner:today"))
    curriculum = client.get(reverse("curriculum:index"))

    assert today.status_code == 200
    assert "/curriculum/start-here/" in today.content.decode()
    assert 'data-testid="start-here-entrypoint"' in today.content.decode()

    assert curriculum.status_code == 200
    assert reverse("curriculum:start_here") in curriculum.content.decode()
    assert 'data-testid="start-here-link"' in curriculum.content.decode()


def test_source_links_are_real_https_urls():
    assert START_HERE_SOURCES
    assert all(source["url"].startswith("https://") for source in START_HERE_SOURCES.values())
