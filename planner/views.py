from datetime import datetime, timedelta

from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import StopWorkSessionForm, StudyBlockEditForm
from .models import RestDay, StudyBlock, WorkSession
from .services import (
    ActiveWorkSessionError,
    carry_forward_unfinished_blocks,
    InvalidWorkSessionStateError,
    generate_weekly_routine,
    format_elapsed_seconds,
    is_weekly_routine_complete,
    is_rest_day,
    move_study_block,
    pause_work_session,
    resume_work_session,
    start_work_session,
    stop_work_session,
    toggle_rest_day,
    WorkSessionTransitionError,
    week_start_for,
)


def _decorate_with_timer_sessions(study_blocks):
    """Attach the latest persisted timer run to each block for template use."""

    study_blocks = list(study_blocks)
    block_ids = [block.pk for block in study_blocks]
    sessions_by_block = {}
    sessions = WorkSession.objects.filter(
        study_block_id__in=block_ids,
    ).order_by("study_block_id", "-created_at", "-id")
    for session in sessions:
        sessions_by_block.setdefault(session.study_block_id, session)

    now = timezone.now()
    for block in study_blocks:
        session = sessions_by_block.get(block.pk)
        block.timer_session = session
        block.timer_elapsed_seconds = (
            session.elapsed_seconds if session else 0
        )
        block.timer_display = format_elapsed_seconds(
            session.elapsed_seconds_at(now) if session else 0
        )
        block.timer_running_since = (
            session.last_resumed_at.isoformat()
            if session and session.status == WorkSession.Status.RUNNING
            else ""
        )
    return study_blocks


def _today_context(today_date=None, timer_error=None):
    today_date = today_date or timezone.localdate()
    carry_forward_unfinished_blocks(today_date)
    rest_day = is_rest_day(today_date)
    all_study_blocks = StudyBlock.objects.filter(date=today_date).order_by(
        "position", "id"
    )
    study_blocks = _decorate_with_timer_sessions(
        [] if rest_day else all_study_blocks
    )
    study_block = (
        study_blocks[0] if study_blocks else None
    )
    return {
        "today": today_date,
        "study_block": study_block,
        "study_blocks": study_blocks,
        "rest_day": rest_day,
        "suppressed_block_count": all_study_blocks.count() if rest_day else 0,
        "routine_generated": is_weekly_routine_complete(today_date),
        "timer_error": timer_error,
    }


def today(request):
    return render(request, "planner/today.html", _today_context())


@require_POST
def generate_weekly_routine_view(request):
    generate_weekly_routine()
    return redirect("planner:today")


def _weekly_plan_context(week_start, forms_by_block=None):
    forms_by_block = forms_by_block or {}
    blocks_by_date = {}
    blocks = _decorate_with_timer_sessions(
        StudyBlock.objects.filter(week_start=week_start).order_by(
            "date", "position", "id"
        )
    )
    for block in blocks:
        blocks_by_date.setdefault(block.date, []).append(block)

    rest_dates = set(
        RestDay.objects.filter(
            date__range=(week_start, week_start + timedelta(days=6))
        ).values_list("date", flat=True)
    )

    days = []
    for day_offset in range(7):
        day_date = week_start + timedelta(days=day_offset)
        day_blocks = blocks_by_date.get(day_date, [])
        day_is_rest = day_date in rest_dates
        day_items = [
            {
                "block": block,
                "form": forms_by_block.get(block.pk)
                or StudyBlockEditForm(instance=block),
            }
            for block in ([] if day_is_rest else day_blocks)
        ]
        days.append(
            {
                "date": day_date,
                "label": day_date.strftime("%A"),
                "items": day_items,
                "is_rest_day": day_is_rest,
                "suppressed_block_count": len(day_blocks) if day_is_rest else 0,
            }
        )

    return {
        "week_start": week_start,
        "week_end": week_start + timedelta(days=6),
        "days": days,
        "routine_generated": is_weekly_routine_complete(week_start),
    }


def weekly_plan(request):
    week_start = week_start_for(timezone.localdate())
    carry_forward_unfinished_blocks(week_start)
    return render(
        request,
        "planner/weekly_plan.html",
        _weekly_plan_context(week_start),
    )


def _parse_day_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


@require_POST
def toggle_rest_day_view(request, day_date):
    parsed_date = _parse_day_date(day_date)
    if parsed_date is None:
        return HttpResponseBadRequest("Use a valid date in YYYY-MM-DD format.")

    toggle_rest_day(parsed_date)
    if request.POST.get("next") == "today":
        return redirect("planner:today")
    return redirect("planner:weekly_plan")


@require_POST
def edit_study_block(request, block_id):
    block = get_object_or_404(StudyBlock, pk=block_id)
    form = StudyBlockEditForm(request.POST, instance=block)
    if form.is_valid():
        form.save()
        return redirect("planner:weekly_plan")

    week_start = block.week_start or week_start_for(block.date)
    context = _weekly_plan_context(week_start, {block.pk: form})
    return render(
        request,
        "planner/weekly_plan.html",
        context,
        status=400,
    )


@require_POST
def reorder_study_block(request, block_id):
    block = get_object_or_404(StudyBlock, pk=block_id)
    direction = request.POST.get("direction", "")
    if direction not in {"up", "down"}:
        return HttpResponseBadRequest("Choose whether to move the block up or down.")

    move_study_block(block, direction)
    return redirect("planner:weekly_plan")


def _timer_error(request, message):
    return render(
        request,
        "planner/today.html",
        _today_context(timer_error=message),
        status=409,
    )


def _active_session_for_block(block):
    return WorkSession.objects.filter(
        study_block=block,
        status__in=(WorkSession.Status.RUNNING, WorkSession.Status.PAUSED),
    ).first()


@require_POST
def start_timer(request, block_id):
    block = get_object_or_404(StudyBlock, pk=block_id)
    try:
        start_work_session(block)
    except ActiveWorkSessionError as error:
        return _timer_error(request, str(error))
    return redirect("planner:today")


@require_POST
def pause_timer(request, block_id):
    block = get_object_or_404(StudyBlock, pk=block_id)
    session = _active_session_for_block(block)
    if session is None:
        return _timer_error(request, "There is no active timer for this study block.")
    try:
        pause_work_session(session)
    except WorkSessionTransitionError as error:
        return _timer_error(request, str(error))
    return redirect("planner:today")


@require_POST
def resume_timer(request, block_id):
    block = get_object_or_404(StudyBlock, pk=block_id)
    session = _active_session_for_block(block)
    if session is None:
        return _timer_error(request, "There is no paused timer for this study block.")
    try:
        resume_work_session(session)
    except InvalidWorkSessionStateError as error:
        return _timer_error(request, str(error))
    return redirect("planner:today")


@require_POST
def stop_timer(request, block_id):
    block = get_object_or_404(StudyBlock, pk=block_id)
    session = _active_session_for_block(block)
    if session is None:
        return _timer_error(request, "There is no active timer for this study block.")

    form = StopWorkSessionForm(request.POST)
    if not form.is_valid():
        return _timer_error(request, "Choose whether this stop completes the block.")

    try:
        stop_work_session(
            session,
            complete_block=form.cleaned_data["complete_block"],
        )
    except WorkSessionTransitionError as error:
        return _timer_error(request, str(error))
    return redirect("planner:today")
