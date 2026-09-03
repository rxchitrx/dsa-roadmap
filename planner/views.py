from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import StudyBlock
from .services import (
    generate_weekly_routine,
    is_weekly_routine_complete,
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
