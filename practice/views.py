import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from problems.models import Problem

from .models import CustomTestCase
from .models import PracticeRun
from .models import SolutionReflection
from .services import CustomTestValidationError
from .services import get_or_create_draft
from .services import run_visible_tests
from .services import save_custom_tests
from .services import save_draft
from .forms import SolutionReflectionForm


def _active_problem(slug: str) -> Problem:
    return get_object_or_404(
        Problem.objects.select_related("concept", "concept__topic"),
        slug=slug,
        is_active=True,
    )


@require_GET
def editor(request, slug):
    problem = _active_problem(slug)
    draft, _created = get_or_create_draft(problem)
    custom_tests = list(CustomTestCase.objects.filter(problem=problem))
    latest_run = (
        PracticeRun.objects.filter(problem=problem)
        .select_related("reflection")
        .first()
    )
    return render(
        request,
        "practice/editor.html",
        {
            "problem": problem,
            "draft": draft,
            "latest_run": latest_run,
            "latest_reflection": getattr(latest_run, "reflection", None),
            "custom_tests": custom_tests,
            "custom_tests_data": [
                {
                    **_custom_test_response(case),
                    "input_json": json.dumps(case.input_data),
                    "expected_json": json.dumps(case.expected_output),
                }
                for case in custom_tests
            ],
        },
    )


@require_http_methods(["GET", "POST"])
def reflection(request, slug, run_id):
    """Write or edit the reflection attached to one exact practice run."""

    problem = _active_problem(slug)
    practice_run = get_object_or_404(
        PracticeRun.objects.select_related("problem"),
        pk=run_id,
        problem=problem,
    )
    existing_reflection = SolutionReflection.objects.filter(
        practice_run=practice_run,
    ).first()
    form = SolutionReflectionForm(
        request.POST if request.method == "POST" else None,
        instance=existing_reflection,
    )

    if request.method == "POST" and form.is_valid():
        saved_reflection = form.save(commit=False)
        saved_reflection.practice_run = practice_run
        saved_reflection.save()
        reflection_url = reverse(
            "practice:reflection",
            kwargs={"slug": problem.slug, "run_id": practice_run.pk},
        )
        return redirect(f"{reflection_url}?saved=1")

    history_snapshot = getattr(practice_run, "history_entry", None)
    return render(
        request,
        "practice/reflection.html",
        {
            "problem": problem,
            "practice_run": practice_run,
            "code_snapshot": (
                history_snapshot.code_snapshot
                if history_snapshot is not None
                else practice_run.code
            ),
            "reflection_form": form,
            "reflection_saved": request.GET.get("saved") == "1",
        },
    )


@require_POST
def save_problem_draft(request, slug):
    problem = _active_problem(slug)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse(
            {"saved": False, "message": "Send draft data as valid JSON."},
            status=400,
        )

    code = payload.get("code") if isinstance(payload, dict) else None
    base_revision = payload.get("base_revision") if isinstance(payload, dict) else None
    if not isinstance(code, str) or isinstance(base_revision, bool):
        return JsonResponse(
            {
                "saved": False,
                "message": "Draft code and base_revision are required.",
            },
            status=400,
        )

    try:
        base_revision = int(base_revision)
    except (TypeError, ValueError):
        return JsonResponse(
            {"saved": False, "message": "base_revision must be an integer."},
            status=400,
        )

    draft, _created = get_or_create_draft(problem)
    result = save_draft(
        problem,
        code=code,
        base_revision=base_revision,
    )
    if not result.saved:
        return JsonResponse(
            {
                "saved": False,
                "stale": True,
                "revision": result.draft.revision,
                "code": result.draft.code,
                "message": "This autosave was based on an older draft.",
            },
            status=409,
        )

    return JsonResponse(
        {
            "saved": True,
            "stale": False,
            "revision": result.draft.revision,
            "updated_at": result.draft.updated_at.isoformat(),
        }
    )


def _custom_test_response(case: CustomTestCase) -> dict:
    return {
        "id": case.pk,
        "label": case.label,
        "input_data": case.input_data,
        "expected_output": case.expected_output,
    }


@require_POST
def save_problem_custom_tests(request, slug):
    problem = _active_problem(slug)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse(
            {
                "saved": False,
                "errors": [
                    {
                        "index": None,
                        "field": "cases",
                        "message": "Send custom tests as valid JSON.",
                        "id": None,
                    }
                ],
            },
            status=400,
        )

    cases = payload.get("cases") if isinstance(payload, dict) else payload
    try:
        saved_cases = save_custom_tests(problem, cases)
    except CustomTestValidationError as error:
        return JsonResponse(
            {"saved": False, "errors": error.errors},
            status=400,
        )

    return JsonResponse(
        {
            "saved": True,
            "cases": [_custom_test_response(case) for case in saved_cases],
            "message": "Custom tests saved.",
        }
    )


@require_POST
def delete_problem_custom_test(request, slug, case_id):
    problem = _active_problem(slug)
    case = CustomTestCase.objects.filter(problem=problem, pk=case_id).first()
    if case is None:
        return JsonResponse(
            {"deleted": False, "message": "That custom test no longer exists."},
            status=404,
        )
    case.delete()
    return JsonResponse({"deleted": True, "id": case_id})


@require_POST
def run_problem_tests(request, slug):
    problem = _active_problem(slug)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse(
            {"run": False, "message": "Send submission data as valid JSON."},
            status=400,
        )

    code = payload.get("code") if isinstance(payload, dict) else None
    if not isinstance(code, str) or not code.strip():
        return JsonResponse(
            {"run": False, "message": "Submit a non-empty Python function."},
            status=400,
        )

    custom_cases = None
    if isinstance(payload, dict) and "custom_tests" in payload:
        try:
            custom_cases = save_custom_tests(problem, payload["custom_tests"])
        except CustomTestValidationError as error:
            return JsonResponse(
                {
                    "run": False,
                    "validation_errors": error.errors,
                    "message": "Fix the custom test cases before execution.",
                },
                status=400,
            )

    try:
        practice_run = run_visible_tests(
            problem,
            code=code,
            custom_cases=custom_cases,
        )
    except CustomTestValidationError as error:
        return JsonResponse(
            {
                "run": False,
                "validation_errors": error.errors,
                "message": "Fix the custom test cases before execution.",
            },
            status=400,
        )
    saved_custom_tests = (
        custom_cases
        if custom_cases is not None
        else CustomTestCase.objects.filter(problem=problem)
    )
    return JsonResponse(
        {
            "run": True,
            "id": practice_run.pk,
            "status": practice_run.status,
            "status_label": practice_run.get_status_display(),
            "summary": practice_run.summary,
            "message": practice_run.message,
            "passed_tests": practice_run.passed_tests,
            "total_tests": practice_run.total_tests,
            "duration_ms": practice_run.duration_ms,
            "details": practice_run.details,
            "custom_tests": [
                _custom_test_response(case) for case in saved_custom_tests
            ],
        }
    )
