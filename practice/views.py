import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from problems.models import Problem

from .services import get_or_create_draft, save_draft


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
    return render(
        request,
        "practice/editor.html",
        {
            "problem": problem,
            "draft": draft,
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
