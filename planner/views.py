from datetime import timedelta

from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import StudyBlockEditForm
from .models import StudyBlock
from .services import (
    generate_weekly_routine,
    is_weekly_routine_complete,
    move_study_block,
    week_start_for,
)


def today(request):
    today_date = timezone.localdate()
    study_blocks = list(
        StudyBlock.objects.filter(date=today_date).order_by("position", "id")
    )
    study_block = (
        study_blocks[0] if study_blocks else None
    )
    return render(
        request,
        "planner/today.html",
        {
            "today": today_date,
            "study_block": study_block,
            "study_blocks": study_blocks,
            "routine_generated": is_weekly_routine_complete(today_date),
        },
    )


@require_POST
def generate_weekly_routine_view(request):
    generate_weekly_routine()
    return redirect("planner:today")


def _weekly_plan_context(week_start, forms_by_block=None):
    forms_by_block = forms_by_block or {}
    blocks_by_date = {}
    blocks = StudyBlock.objects.filter(week_start=week_start).order_by(
        "date", "position", "id"
    )
    for block in blocks:
        blocks_by_date.setdefault(block.date, []).append(block)

    days = []
    for day_offset in range(7):
        day_date = week_start + timedelta(days=day_offset)
        day_items = [
            {
                "block": block,
                "form": forms_by_block.get(block.pk)
                or StudyBlockEditForm(instance=block),
            }
            for block in blocks_by_date.get(day_date, [])
        ]
        days.append(
            {
                "date": day_date,
                "label": day_date.strftime("%A"),
                "items": day_items,
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
    return render(
        request,
        "planner/weekly_plan.html",
        _weekly_plan_context(week_start),
    )


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
