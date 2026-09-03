from datetime import datetime, timedelta

from django.http import HttpResponse, HttpResponseBadRequest
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from problems.models import CatalogSync, Problem
from reviews.services import due_review_queue

from .forms import StopWorkSessionForm, StudyBlockEditForm
from .models import RestDay, StudyBlock, WorkSession
from .services import (
    ActiveWorkSessionError,
    assign_weekday_problems,
    carry_forward_unfinished_blocks,
    InvalidWorkSessionStateError,
    assign_recommended_concept,
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
from .summary import get_weekly_summary
from .analytics import get_progress_analytics, resolve_analytics_range
from .backup import (
    BackupRestoreError,
    BackupValidationError,
    export_backup_json,
    restore_backup,
)
from .exports import export_weekly_csv
from .next_week import (
    NextWeekPlanError,
    edit_next_week_plan,
    generate_next_week_plan,
    save_next_week_plan,
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


def _week_calendar(today_date):
    """Build the compact seven-day planner strip shown on Today."""

    week_start = week_start_for(today_date)
    week_end = week_start + timedelta(days=6)
    blocks_by_date = {}
    for block in StudyBlock.objects.filter(
        date__range=(week_start, week_end),
    ).order_by("date", "position", "id"):
        blocks_by_date.setdefault(block.date, []).append(block)

    rest_dates = set(
        RestDay.objects.filter(date__range=(week_start, week_end)).values_list(
            "date", flat=True
        )
    )
    days = []
    for offset in range(7):
        day_date = week_start + timedelta(days=offset)
        day_blocks = blocks_by_date.get(day_date, [])
        pending_blocks = [
            block
            for block in day_blocks
            if block.status != StudyBlock.Status.COMPLETED
        ]
        days.append(
            {
                "date": day_date,
                "weekday": day_date.strftime("%a"),
                "day_number": day_date.day,
                "is_selected": day_date == today_date,
                "is_rest_day": day_date in rest_dates,
                "block_count": len(day_blocks),
                "completed_count": len(day_blocks) - len(pending_blocks),
                "planned_minutes": sum(
                    block.planned_minutes for block in day_blocks
                ),
                "next_title": pending_blocks[0].title if pending_blocks else "",
            }
        )
    return {
        "week_start": week_start,
        "week_end": week_end,
        "days": days,
    }


def _today_context(today_date=None, timer_error=None):
    today_date = today_date or timezone.localdate()
    carry_forward_unfinished_blocks(today_date)
    assign_recommended_concept(today_date)
    assign_weekday_problems(today_date)
    rest_day = is_rest_day(today_date)
    all_study_blocks = (
        StudyBlock.objects.select_related("assigned_concept__topic")
        .prefetch_related("problem_assignments__problem")
        .filter(date=today_date)
        .order_by("position", "id")
    )
    study_blocks = _decorate_with_timer_sessions(
        [] if rest_day else all_study_blocks
    )
    for sequence_number, block in enumerate(study_blocks, start=1):
        block.sequence_number = sequence_number
    routine_generated = is_weekly_routine_complete(today_date)
    due_reviews = list(due_review_queue()) if today_date.weekday() < 5 else []
    deferred_review_blocks = [
        block
        for block in study_blocks
        if (
            block.status != StudyBlock.Status.COMPLETED
            and block.routine_key
            and block.routine_key.endswith("-review")
            and not due_reviews
        )
    ]
    action_blocks = [
        block for block in study_blocks if block not in deferred_review_blocks
    ]
    for sequence_number, block in enumerate(action_blocks, start=1):
        block.sequence_number = sequence_number
    pending_blocks = [
        block
        for block in action_blocks
        if block.status != StudyBlock.Status.COMPLETED
    ]
    completed_blocks = [
        block
        for block in action_blocks
        if block.status == StudyBlock.Status.COMPLETED
    ]
    study_block = action_blocks[0] if action_blocks else None
    next_step_block = pending_blocks[0] if pending_blocks else None
    upcoming_blocks = pending_blocks[1:] if next_step_block else []
    is_next_step_review = bool(
        next_step_block
        and next_step_block.routine_key
        and next_step_block.routine_key.endswith("-review")
    )
    is_weekday = today_date.weekday() < 5
    is_sunday = today_date.weekday() == 6
    return {
        "today": today_date,
        "study_block": study_block,
        "study_blocks": study_blocks,
        "next_step_block": next_step_block,
        "next_review": due_reviews[0] if due_reviews else None,
        "is_next_step_review": is_next_step_review,
        "upcoming_blocks": upcoming_blocks,
        "completed_blocks": completed_blocks,
        "sequence_total": len(action_blocks),
        "deferred_review_block": deferred_review_blocks[0] if deferred_review_blocks else None,
        "rest_day": rest_day,
        "suppressed_block_count": all_study_blocks.count() if rest_day else 0,
        "routine_generated": routine_generated,
        "timer_error": timer_error,
        "is_weekday": is_weekday,
        "is_sunday": is_sunday,
        "due_reviews": due_reviews,
        "week_calendar": _week_calendar(today_date),
        "active_problem_count": Problem.objects.filter(is_active=True).count(),
        "catalog_sync": CatalogSync.objects.first(),
    }


def today(request):
    raw_date = request.GET.get("date")
    selected_date = _parse_day_date(raw_date) if raw_date else timezone.localdate()
    if raw_date and selected_date is None:
        return HttpResponseBadRequest("Use a valid date in YYYY-MM-DD format.")
    return render(request, "planner/today.html", _today_context(selected_date))


@require_GET
def weekly_summary(request):
    raw_week = request.GET.get("week")
    if raw_week:
        requested_date = _parse_day_date(raw_week)
        if requested_date is None:
            return HttpResponseBadRequest("Use a valid week date in YYYY-MM-DD format.")
    else:
        requested_date = timezone.localdate()

    summary = get_weekly_summary(week_start_for(requested_date))
    for action in summary["next_actions"]:
        if action["key"] == "unfinished_blocks":
            action["url"] = reverse("planner:weekly_plan")
        elif action["key"] == "due_reviews":
            action["url"] = reverse("reviews:due_queue")
        elif action["key"] == "assessment_mistakes":
            action["url"] = reverse(
                "assessments:assessment_mistakes",
                kwargs={"session_id": action["session_id"]},
            )
        else:
            action["url"] = reverse("planner:today")

    return render(
        request,
        "planner/weekly_summary.html",
        {
            "summary": summary,
            "previous_week": summary["week_start"] - timedelta(days=7),
            "next_week": summary["week_start"] + timedelta(days=7),
        },
    )


@require_GET
def progress_analytics(request):
    """Render detailed evidence for an inclusive local-date range."""

    raw_start = request.GET.get("start")
    raw_end = request.GET.get("end")
    start = _parse_day_date(raw_start) if raw_start else None
    end = _parse_day_date(raw_end) if raw_end else None
    if (raw_start and start is None) or (raw_end and end is None):
        return HttpResponseBadRequest("Use valid start and end dates in YYYY-MM-DD format.")
    try:
        window = resolve_analytics_range(start, end)
    except ValueError as error:
        return HttpResponseBadRequest(str(error))
    analytics = get_progress_analytics(
        window.start_date,
        window.end_date,
    )
    return render(
        request,
        "planner/analytics.html",
        {"analytics": analytics},
    )


@require_GET
def weekly_csv_export(request):
    """Download the import-friendly CSV for the selected calendar week."""

    raw_week = request.GET.get("week")
    selected_date = _parse_day_date(raw_week) if raw_week else None
    if raw_week and selected_date is None:
        return HttpResponseBadRequest("Use a valid week date in YYYY-MM-DD format.")
    week_start = week_start_for(selected_date or timezone.localdate())
    response = HttpResponse(
        export_weekly_csv(selected_date),
        content_type="text/csv; charset=utf-8",
    )
    response["Content-Disposition"] = (
        f'attachment; filename="dsa-roadmap-week-{week_start.isoformat()}.csv"'
    )
    return response


@require_GET
def backup_center(request):
    return render(request, "planner/backup.html")


@require_GET
def backup_export(request):
    response = HttpResponse(
        export_backup_json(),
        content_type="application/json; charset=utf-8",
    )
    response["Content-Disposition"] = 'attachment; filename="dsa-roadmap-backup.json"'
    return response


@require_POST
def backup_restore(request):
    upload = request.FILES.get("backup")
    if upload is None:
        return render(
            request,
            "planner/backup.html",
            {"backup_error": "Choose a JSON backup file first."},
            status=400,
        )
    try:
        result = restore_backup(upload)
    except (BackupValidationError, BackupRestoreError, ValidationError) as error:
        return render(
            request,
            "planner/backup.html",
            {"backup_error": str(error)},
            status=400,
        )
    return render(
        request,
        "planner/backup.html",
        {"restored": True, "safety_export_path": result.safety_export_path.name},
    )


def _next_week_form_edits(request, plan):
    edits = {}
    for block in plan.blocks:
        prefix = f"block__{block.key}__"
        title = request.POST.get(f"{prefix}title")
        minutes = request.POST.get(f"{prefix}planned_minutes")
        block_date = request.POST.get(f"{prefix}date")
        changes = {}
        if title is not None:
            changes["title"] = title
        if minutes is not None:
            changes["planned_minutes"] = minutes
        if block_date is not None:
            parsed_date = _parse_day_date(block_date)
            if parsed_date is None:
                raise NextWeekPlanError("Use valid dates for every planned block.")
            changes["date"] = parsed_date
        if changes:
            edits[block.key] = changes
    return edits


@require_GET
def next_week_plan_preview(request):
    """Show the generated, editable preview for the next calendar week."""

    raw_week = request.GET.get("week")
    target_week = _parse_day_date(raw_week) if raw_week else None
    if raw_week and target_week is None:
        return HttpResponseBadRequest("Use a valid week date in YYYY-MM-DD format.")
    plan = generate_next_week_plan(target_week_start=target_week)
    return render(
        request,
        "planner/next_week.html",
        {
            "plan": plan,
            "week_end": plan.week_start + timedelta(days=6),
            "saved": False,
        },
    )


@require_POST
def save_next_week_plan_view(request):
    """Validate and save edits from the next-week preview form."""

    raw_week = request.POST.get("week")
    target_week = _parse_day_date(raw_week) if raw_week else None
    if raw_week and target_week is None:
        return HttpResponseBadRequest("Use a valid week date in YYYY-MM-DD format.")
    try:
        plan = generate_next_week_plan(target_week_start=target_week)
        edits = _next_week_form_edits(request, plan)
        edited_plan = edit_next_week_plan(plan, edits)
        saved_plan = save_next_week_plan(edited_plan)
    except NextWeekPlanError as error:
        plan = generate_next_week_plan(target_week_start=target_week)
        return render(
            request,
            "planner/next_week.html",
            {
                "plan": plan,
                "week_end": plan.week_start + timedelta(days=6),
                "saved": False,
                "plan_error": str(error),
            },
            status=400,
        )
    return render(
        request,
        "planner/next_week.html",
        {
            "plan": saved_plan,
            "week_end": saved_plan.week_start + timedelta(days=6),
            "saved": True,
        },
    )


@require_POST
def generate_weekly_routine_view(request):
    generate_weekly_routine()
    return redirect("planner:today")


def _weekly_plan_context(week_start, forms_by_block=None):
    forms_by_block = forms_by_block or {}
    blocks_by_date = {}
    blocks = _decorate_with_timer_sessions(
        StudyBlock.objects.select_related("assigned_concept__topic")
        .prefetch_related("problem_assignments__problem")
        .filter(week_start=week_start)
        .order_by("date", "position", "id")
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
    assign_recommended_concept(timezone.localdate())
    assign_weekday_problems(week_start)
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
