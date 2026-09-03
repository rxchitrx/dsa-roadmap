from datetime import datetime

from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .models import AssessmentPool, AssessmentResponse, AssessmentSession
from .services import (
    AssessmentUnavailable,
    generate_saturday_assessment_pool,
    get_assessment_summary,
    navigate_assessment,
    refresh_assessment_session,
    save_assessment_response,
    start_saturday_assessment,
    submit_assessment,
    week_start_for,
)


def _parse_week_start(value):
    if not value:
        return timezone.localdate()
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


@require_GET
def saturday_pool(request):
    requested_date = _parse_week_start(request.GET.get("week"))
    if requested_date is None:
        return HttpResponseBadRequest("Use a valid week date in YYYY-MM-DD format.")

    week_start = week_start_for(requested_date)
    pool = generate_saturday_assessment_pool(week_start)
    pool = AssessmentPool.objects.prefetch_related(
        "selections__problem",
    ).get(pk=pool.pk)
    session = AssessmentSession.objects.filter(pool=pool).first()
    return render(
        request,
        "assessments/saturday_pool.html",
        {
            "pool": pool,
            "week_start": week_start,
            "selections": pool.selections.all(),
            "session": session,
        },
    )


@require_POST
def start_assessment(request):
    requested_date = _parse_week_start(request.POST.get("week"))
    if requested_date is None:
        return HttpResponseBadRequest("Use a valid week date in YYYY-MM-DD format.")
    try:
        session = start_saturday_assessment(week_start_for(requested_date))
    except AssessmentUnavailable as error:
        return HttpResponseBadRequest(str(error))
    return redirect("assessments:assessment_session", session_id=session.pk)


def _posted_position(request, fallback: int) -> int:
    try:
        return int(request.POST.get("target_position", fallback))
    except (TypeError, ValueError):
        return fallback


@require_http_methods(["GET", "POST"])
def assessment_session(request, session_id: int):
    session = get_object_or_404(
        AssessmentSession.objects.select_related("pool"),
        pk=session_id,
    )
    if request.method == "POST":
        action = request.POST.get("action", "save")
        try:
            save_assessment_response(
                session,
                session.current_position,
                draft_answer=request.POST.get("draft_answer", ""),
                outcome=request.POST.get(
                    "outcome", AssessmentResponse.Outcome.NOT_STARTED
                ),
                result_note=request.POST.get("result_note", ""),
            )
            if action == "submit":
                submit_assessment(session)
            elif action in {"previous", "next", "goto"}:
                current = session.current_position
                target = _posted_position(
                    request,
                    current - 1 if action == "previous" else current + 1,
                )
                navigate_assessment(session, target)
        except (AssessmentResponse.DoesNotExist, AssessmentUnavailable, ValueError) as error:
            return HttpResponseBadRequest(str(error))
        return redirect("assessments:assessment_session", session_id=session.pk)

    session = refresh_assessment_session(session)
    responses = list(
        session.responses.select_related("selection__problem").order_by(
            "selection__position", "id"
        )
    )
    if not responses:
        return HttpResponseBadRequest("This assessment has no Problem responses.")
    current_index = min(session.current_position, len(responses)) - 1
    current_response = responses[current_index]
    remaining_seconds = (
        max(0, int((session.cutoff_at - timezone.now()).total_seconds()))
        if session.status == AssessmentSession.Status.IN_PROGRESS
        else 0
    )
    summary = session.final_summary or get_assessment_summary(session)
    return render(
        request,
        "assessments/assessment_session.html",
        {
            "session": session,
            "responses": responses,
            "current_response": current_response,
            "remaining_seconds": remaining_seconds,
            "summary": summary,
            "outcomes": AssessmentResponse.Outcome.choices,
        },
    )
