from urllib.parse import urlsplit

from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from curriculum.models import Concept, Topic

from .forms import ProblemClassificationForm
from .catalog_sync import CatalogSyncError, sync_catalog as run_catalog_sync
from .models import CatalogSync, Problem, ProblemClassification
from .services import add_classification, remove_classification


def _safe_external_url(value: str) -> str:
    """Return only absolute HTTP(S) URLs suitable for an external link."""

    if not value or any(character.isspace() for character in value):
        return ""

    try:
        parsed = urlsplit(value)
    except ValueError:
        return ""

    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return ""

    try:
        if not parsed.hostname or parsed.username or parsed.password:
            return ""
    except ValueError:
        return ""

    return value


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
            "latest_sync": CatalogSync.objects.first(),
            "last_successful_sync": CatalogSync.objects.filter(
                status=CatalogSync.Status.SUCCEEDED
            ).first(),
        },
    )


@require_POST
def sync_catalog(request):
    """Start a public LeetCode sync and return to the safe local catalog."""

    try:
        run_catalog_sync()
    except CatalogSyncError as exc:
        messages.error(request, f"LeetCode catalog sync failed: {exc}")
    else:
        messages.success(request, "LeetCode catalog sync completed.")
    return redirect("problems:index")


def catalog_sync_status(request):
    """Expose the persisted progress state for a lightweight status poll."""

    run = CatalogSync.objects.first()
    if run is None:
        return JsonResponse({"status": "never_run", "message": "No catalog sync has run yet."})

    return JsonResponse(
        {
            "status": run.status,
            "label": run.get_status_display(),
            "progress": run.progress_label,
            "processed_items": run.processed_items,
            "total_items": run.total_items,
            "imported_count": run.imported_count,
            "updated_count": run.updated_count,
            "classification_warning_count": run.classification_warning_count,
            "error_message": run.error_message,
            "last_success_at": (
                run.last_success_at.isoformat() if run.last_success_at else None
            ),
        }
    )


def problem_detail(request, slug):
    """Render one active problem with its practice and source context."""

    problem = get_object_or_404(
        Problem.objects.select_related("concept", "concept__topic"),
        slug=slug,
        is_active=True,
    )
    return render(
        request,
        "problems/detail.html",
        _problem_detail_context(problem),
    )


@require_POST
def add_problem_classification(request, slug):
    problem = get_object_or_404(
        Problem.objects.select_related("concept", "concept__topic"),
        slug=slug,
        is_active=True,
    )
    form = ProblemClassificationForm(request.POST, problem=problem)
    if form.is_valid():
        add_classification(
            problem,
            form.cleaned_data["concept"],
            status=form.cleaned_data["status"],
            note=form.cleaned_data["note"],
        )
        return redirect("problems:detail", slug=problem.slug)

    return render(
        request,
        "problems/detail.html",
        _problem_detail_context(problem, classification_form=form),
        status=400,
    )


@require_POST
def remove_problem_classification(request, slug, classification_id):
    problem = get_object_or_404(Problem, slug=slug, is_active=True)
    classification = get_object_or_404(
        ProblemClassification,
        pk=classification_id,
        problem=problem,
    )
    remove_classification(problem, classification)
    return redirect("problems:detail", slug=problem.slug)


def _problem_detail_context(problem, *, classification_form=None):
    constraints = getattr(problem, "constraints", "")
    complexity = getattr(problem, "expected_complexity", "") or getattr(
        problem, "complexity", ""
    )
    if not complexity and problem.concept:
        complexity = problem.concept.complexity_notes

    return {
        "problem": problem,
        "active_snapshot": problem.active_snapshot,
        "constraints": constraints,
        "complexity": complexity,
        "safe_source_url": _safe_external_url(problem.source_url),
        "classifications": problem.classifications.select_related(
            "concept", "concept__topic"
        ),
        "classification_form": classification_form
        or ProblemClassificationForm(problem=problem),
    }
