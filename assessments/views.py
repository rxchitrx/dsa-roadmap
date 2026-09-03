from datetime import datetime

from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import AssessmentMistakeForm
from .models import AssessmentPool, AssessmentResponse, AssessmentSession
from .services import (
    AssessmentUnavailable,
    generate_assessment_mistakes,
    generate_saturday_assessment_pool,
    get_assessment_summary,
    navigate_assessment,
    refresh_assessment_session,
    save_assessment_mistake,
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


@require_http_methods(["GET", "POST"])
def assessment_mistakes(request, session_id: int):
    """Review the failed or skipped Problems from one Assessment."""

    assessment = get_object_or_404(
        AssessmentSession.objects.select_related("pool"),
        pk=session_id,
    )
    generate_assessment_mistakes(assessment)
    mistakes = list(
        assessment.mistakes.select_related("problem", "response")
        .order_by("response__selection__position", "id")
    )
    forms_by_mistake = {}

    if request.method == "POST":
        try:
            mistake_id = int(request.POST.get("mistake", ""))
        except (TypeError, ValueError):
            return HttpResponseBadRequest("Choose a valid assessment mistake.")
        mistake = next((item for item in mistakes if item.pk == mistake_id), None)
        if mistake is None:
            return HttpResponseBadRequest("That assessment mistake does not exist.")

        form = AssessmentMistakeForm(request.POST, instance=mistake)
        action = request.POST.get("action", "save")
        if action not in {"save", "complete", "incomplete"}:
            return HttpResponseBadRequest("Choose a valid mistake action.")
        if form.is_valid():
            save_assessment_mistake(
                mistake,
                cause=form.cleaned_data["cause"],
                corrected_approach=form.cleaned_data["corrected_approach"],
                next_action=form.cleaned_data["next_action"],
                is_complete=(
                    True if action == "complete" else
                    False if action == "incomplete" else None
                ),
            )
            return redirect(
                f"{reverse('assessments:assessment_mistakes', kwargs={'session_id': assessment.pk})}?saved=1"
            )
        forms_by_mistake[mistake.pk] = form

    mistake_items = [
        {
            "mistake": mistake,
            "form": forms_by_mistake.get(
                mistake.pk,
                AssessmentMistakeForm(instance=mistake),
            ),
        }
        for mistake in mistakes
    ]
    return render(
        request,
        "assessments/assessment_mistakes.html",
        {
            "assessment": assessment,
            "mistake_items": mistake_items,
            "mistake_count": len(mistakes),
            "complete_count": sum(mistake.is_complete for mistake in mistakes),
            "mistake_saved": request.GET.get("saved") == "1",
        },
    )
