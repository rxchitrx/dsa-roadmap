from django.db.models import Q
from django.shortcuts import render

from curriculum.models import Concept, Topic

from .models import Problem


def problems_index(request):
    """Render the local problem catalog with composable GET filters."""

    search_query = request.GET.get("q", "").strip()
    selected_topic = request.GET.get("topic", "").strip()
    selected_concept = request.GET.get("concept", "").strip()
    selected_difficulty = request.GET.get("difficulty", "").strip()

    all_active_problems = Problem.objects.filter(is_active=True)
    problems = all_active_problems.select_related("concept", "concept__topic")

    if search_query:
        problems = problems.filter(
            Q(title__icontains=search_query)
            | Q(statement__icontains=search_query)
            | Q(source_name__icontains=search_query)
            | Q(source_problem_id__icontains=search_query)
        )

    if selected_topic:
        problems = problems.filter(concept__topic__slug=selected_topic)

    if selected_concept:
        problems = problems.filter(concept__slug=selected_concept)

    valid_difficulties = {value for value, _label in Problem.Difficulty.choices}
    if selected_difficulty in valid_difficulties:
        problems = problems.filter(difficulty=selected_difficulty)
    elif selected_difficulty == "unknown":
        problems = problems.filter(Q(difficulty="") | Q(difficulty__isnull=True))
    elif selected_difficulty:
        # Treat stale query-string values as no difficulty filter rather than
        # making the catalog look empty after a choice is renamed.
        selected_difficulty = ""

    problems = problems.order_by("title", "id")
    missing_metadata_count = all_active_problems.filter(
        Q(concept__isnull=True)
        | Q(difficulty="")
        | Q(difficulty__isnull=True)
        | Q(source_name="")
    ).count()

    return render(
        request,
        "problems/index.html",
        {
            "problems": problems,
            "result_count": problems.count(),
            "catalog_count": all_active_problems.count(),
            "missing_metadata_count": missing_metadata_count,
            "search_query": search_query,
            "selected_topic": selected_topic,
            "selected_concept": selected_concept,
            "selected_difficulty": selected_difficulty,
            "topics": Topic.objects.order_by("display_order", "name", "id"),
            "concepts": Concept.objects.select_related("topic").order_by(
                "topic__display_order", "order", "name", "id"
            ),
            "difficulties": Problem.Difficulty.choices,
            "has_filters": bool(
                search_query
                or selected_topic
                or selected_concept
                or selected_difficulty
            ),
        },
    )
