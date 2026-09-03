from django.shortcuts import render
from django.views.decorators.http import require_GET

from problems.models import Problem

from .services import history_for_problem


@require_GET
def index(request):
    selected_problem = request.GET.get("problem", "").strip()
    entries = history_for_problem(selected_problem)
    problems = (
        Problem.objects.filter(practice_runs__isnull=False, is_active=True)
        .distinct()
        .order_by("title", "id")
    )
    return render(
        request,
        "history/index.html",
        {
            "entries": entries,
            "problems": problems,
            "selected_problem": selected_problem,
            "entry_count": len(entries),
        },
    )
